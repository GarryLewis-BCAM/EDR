"""
Network Connection Tracker with IP Geolocation
Tracks all network connections, maps IPs to locations, detects threats
"""
import psutil
import time
import socket
import requests
import platform
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


class NetworkTracker:
    """Track network connections and geolocate IPs"""
    
    def __init__(self, config: dict, logger, db):
        self.config = config
        self.logger = logger
        self.db = db
        self.connection_history = {}
        self.ip_cache = {}  # Cache geolocation lookups
        self.threat_ips = set()  # Known malicious IPs
        self.failed_pids = set()  # PIDs that consistently fail permission checks
        self.is_macos = platform.system() == 'Darwin'
        self.collection_errors = 0
        self.max_collection_errors = 10  # Switch to fallback after 10 errors
        self.use_fallback = False
        
        # NAS IP to monitor (exempt from local filtering)
        self.nas_ip = config.get('nas', {}).get('ip', '192.168.1.80')
        
        # Warn about macOS limitations
        if self.is_macos:
            self.logger.warning(
                "Running on macOS: psutil.net_connections() requires root. Using per-process enumeration fallback."
            )
        
        # Known safe networks (to reduce noise)
        self.safe_networks = [
            '10.', '172.16.', '192.168.', '127.',  # Private IPs
            '::1',  # IPv6 localhost
            '::ffff:127.',  # IPv4-mapped IPv6 localhost
            'fe80::', 'fc00::', 'fd00::',  # IPv6 private
        ]
        
        # Suspicious ports
        self.suspicious_ports = [
            21,    # FTP
            23,    # Telnet
            135,   # RPC
            139,   # NetBIOS
            445,   # SMB
            1433,  # MSSQL
            3306,  # MySQL
            3389,  # RDP
            5432,  # PostgreSQL
            6379,  # Redis
            27017, # MongoDB
        ]
    
    def collect(self) -> List[Dict]:
        """Collect all network connections with geolocation"""
        events = []
        
        # Use fallback method if too many errors or on macOS without root
        if self.use_fallback or (self.is_macos and self.collection_errors > 3):
            return self._collect_via_process_iteration()
        
        try:
            connections = psutil.net_connections(kind='inet')
            self.collection_errors = 0  # Reset on success
            
            for conn in connections:
                try:
                    # Skip if no remote address
                    if not conn.raddr:
                        continue
                    
                    remote_ip = conn.raddr.ip
                    remote_port = conn.raddr.port
                    local_port = conn.laddr.port if conn.laddr else 0
                    
                    # Skip local/private IPs (except NAS)
                    if self._is_safe_ip(remote_ip) and remote_ip != self.nas_ip:
                        continue
                    
                    # Get process info
                    process_name = 'unknown'
                    process_pid = conn.pid
                    if conn.pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            process_name = proc.name()
                        except:
                            pass
                    
                    # Geolocate IP
                    geo_data = self._geolocate_ip(remote_ip)
                    
                    # Calculate threat score
                    threat_score = self._calculate_threat_score(
                        remote_ip, remote_port, local_port, 
                        conn.status, process_name
                    )
                    
                    event = {
                        'timestamp': time.time(),
                        'source_ip': conn.laddr.ip if conn.laddr else None,
                        'source_port': local_port,
                        'dest_ip': remote_ip,
                        'dest_port': remote_port,
                        'protocol': 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP',
                        'status': conn.status,
                        'process_name': process_name,
                        'process_pid': process_pid,
                        'country': geo_data.get('country'),
                        'city': geo_data.get('city'),
                        'latitude': geo_data.get('latitude'),
                        'longitude': geo_data.get('longitude'),
                        'threat_score': threat_score,
                        'is_suspicious': threat_score > 50,
                        'direction': 'outbound'  # We're connecting out
                    }
                    
                    events.append(event)
                    
                    # Store in database
                    self.db.insert_network_event(event)
                    
                    # Log high-threat connections
                    if threat_score > 70:
                        self.logger.warning(
                            f"High-threat connection: {process_name} → {remote_ip}:{remote_port} "
                            f"({geo_data.get('country', 'Unknown')}) Score: {threat_score}"
                        )
                    
                except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                    # Expected on some processes, don't log as error
                    self.logger.debug(f"Permission denied for connection: {e}")
                    continue
                except Exception as e:
                    self.logger.debug(f"Error processing connection: {e}")
                    continue
        
        except psutil.AccessDenied as e:
            self.collection_errors += 1
            self.logger.warning(
                f"Network collection AccessDenied (attempt {self.collection_errors}): {e}. Switching to per-process enumeration."
            )
            # Switch to fallback immediately on macOS or after too many failures
            if self.is_macos or self.collection_errors >= self.max_collection_errors:
                self.use_fallback = True
                return self._collect_via_process_iteration()
        except Exception as e:
            self.collection_errors += 1
            self.logger.error(f"Network collection error ({self.collection_errors}): {e}")
            if self.collection_errors >= self.max_collection_errors:
                self.logger.warning("Too many network collection errors, switching to fallback")
                self.use_fallback = True
        
        return events
    
    def _geolocate_ip(self, ip: str) -> Dict:
        """Get geolocation data for IP address"""
        
        # Check cache first
        if ip in self.ip_cache:
            return self.ip_cache[ip]
        
        geo_data = {
            'country': 'Unknown',
            'city': 'Unknown',
            'latitude': 0.0,
            'longitude': 0.0,
            'isp': 'Unknown'
        }
        
        try:
            # Use ip-api.com (free, no key required, 45 req/min limit)
            response = requests.get(
                f'http://ip-api.com/json/{ip}',
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    geo_data = {
                        'country': data.get('country', 'Unknown'),
                        'country_code': data.get('countryCode', 'XX'),
                        'city': data.get('city', 'Unknown'),
                        'latitude': data.get('lat', 0.0),
                        'longitude': data.get('lon', 0.0),
                        'isp': data.get('isp', 'Unknown'),
                        'org': data.get('org', 'Unknown'),
                        'as': data.get('as', 'Unknown'),
                    }
                    
                    # Cache it
                    self.ip_cache[ip] = geo_data
        
        except Exception as e:
            self.logger.debug(f"Geolocation failed for {ip}: {e}")
        
        return geo_data
    
    def _calculate_threat_score(self, ip: str, remote_port: int, 
                                local_port: int, status: str, 
                                process_name: str) -> float:
        """Calculate threat score for connection"""
        score = 0.0
        
        # Known malicious IP
        if ip in self.threat_ips:
            score += 80
        
        # Suspicious ports
        if remote_port in self.suspicious_ports:
            score += 30
        if local_port in self.suspicious_ports:
            score += 20
        
        # Connection state (ESTABLISHED is less suspicious than SYN_SENT)
        if status in ['SYN_SENT', 'SYN_RECV']:
            score += 10
        
        # Suspicious process names
        suspicious_procs = ['nc', 'netcat', 'nmap', 'masscan', 'hping']
        if any(sus in process_name.lower() for sus in suspicious_procs):
            score += 40
        
        # Uncommon ports (not 80, 443, 22, etc.)
        common_ports = [80, 443, 22, 25, 53, 110, 143, 993, 995]
        if remote_port not in common_ports and remote_port > 1024:
            score += 5
        
        return min(score, 100)
    
    def _is_safe_ip(self, ip: str) -> bool:
        """Check if IP is in safe/private range"""
        return any(ip.startswith(net) for net in self.safe_networks)
    
    def _collect_via_process_iteration(self) -> List[Dict]:
        """Fallback: Collect connections by iterating through processes"""
        events = []
        
        try:
            # Iterate through all processes
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pid = proc.info['pid']
                    
                    # Skip PIDs that consistently fail
                    if pid in self.failed_pids:
                        continue
                    
                    # Get connections for this specific process
                    try:
                        connections = proc.net_connections(kind='inet')
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        # Mark as failed and skip
                        self.failed_pids.add(pid)
                        continue
                    
                    process_name = proc.info.get('name', 'unknown')
                    
                    for conn in connections:
                        try:
                            # Skip if no remote address
                            if not conn.raddr:
                                continue
                            
                            remote_ip = conn.raddr.ip
                            remote_port = conn.raddr.port
                            local_port = conn.laddr.port if conn.laddr else 0
                            
                            # Skip local/private IPs (except NAS)
                            if self._is_safe_ip(remote_ip) and remote_ip != self.nas_ip:
                                continue
                            
                            # Geolocate IP
                            geo_data = self._geolocate_ip(remote_ip)
                            
                            # Calculate threat score
                            threat_score = self._calculate_threat_score(
                                remote_ip, remote_port, local_port, 
                                conn.status, process_name
                            )
                            
                            event = {
                                'timestamp': time.time(),
                                'source_ip': conn.laddr.ip if conn.laddr else None,
                                'source_port': local_port,
                                'dest_ip': remote_ip,
                                'dest_port': remote_port,
                                'protocol': 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP',
                                'status': conn.status,
                                'process_name': process_name,
                                'process_pid': pid,
                                'country': geo_data.get('country'),
                                'city': geo_data.get('city'),
                                'latitude': geo_data.get('latitude'),
                                'longitude': geo_data.get('longitude'),
                                'threat_score': threat_score,
                                'is_suspicious': threat_score > 50,
                                'direction': 'outbound'
                            }
                            
                            events.append(event)
                            
                            # Store in database
                            try:
                                self.db.insert_network_event(event)
                            except Exception as e:
                                self.logger.debug(f"Failed to insert network event: {e}")
                            
                            # Log high-threat connections
                            if threat_score > 70:
                                self.logger.warning(
                                    f"High-threat connection: {process_name} → {remote_ip}:{remote_port} "
                                    f"({geo_data.get('country', 'Unknown')}) Score: {threat_score}"
                                )
                        
                        except Exception as e:
                            self.logger.debug(f"Error processing connection: {e}")
                            continue
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    self.logger.debug(f"Error processing process: {e}")
                    continue
            
            # Cleanup failed_pids cache periodically (keep last 1000)
            if len(self.failed_pids) > 1000:
                self.failed_pids = set(list(self.failed_pids)[-500:])
        
        except Exception as e:
            self.logger.error(f"Process iteration collection error: {e}")
        
        return events
    
    def get_threat_map_data(self, hours: int = 24) -> List[Dict]:
        """Get threat data formatted for world map visualization"""
        try:
            conn = self.db._get_connection()
            cutoff = time.time() - (hours * 3600)
            
            cursor = conn.execute('''
                SELECT dest_ip, dest_port, country, city, latitude, longitude,
                       process_name, threat_score, COUNT(*) as connection_count,
                       MAX(timestamp) as last_seen
                FROM network_events
                WHERE timestamp > ? AND is_suspicious = 1
                GROUP BY dest_ip, country
                ORDER BY threat_score DESC, connection_count DESC
                LIMIT 100
            ''', (cutoff,))
            
            threats = []
            for row in cursor.fetchall():
                threats.append({
                    'ip': row[0],
                    'port': row[1],
                    'country': row[2],
                    'city': row[3],
                    'lat': row[4],
                    'lon': row[5],
                    'process': row[6],
                    'threat_score': row[7],
                    'count': row[8],
                    'last_seen': row[9]
                })
            
            return threats
        
        except Exception as e:
            self.logger.error(f"Failed to get threat map data: {e}")
            return []
