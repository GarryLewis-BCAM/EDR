"""
macOS Native Network Tracker
Uses lsof and netstat for full system-wide network visibility without root
Alternative to psutil.net_connections() which requires root on macOS
"""
import subprocess
import re
import time
import socket
from typing import Dict, List, Optional
from datetime import datetime


class MacOSNativeNetworkTracker:
    """
    Network tracker using macOS native tools (lsof, netstat)
    Provides full system-wide visibility without requiring root privileges
    """
    
    def __init__(self, config: dict, logger, db):
        self.config = config
        self.logger = logger
        self.db = db
        self.ip_cache = {}
        self.connection_history = {}
        
        # NAS IP to monitor (exempt from local filtering)
        self.nas_ip = config.get('nas', {}).get('ip', '192.168.1.80')
        
        # Known safe networks
        self.safe_networks = [
            '10.', '172.16.', '192.168.', '127.',
            'fe80::', 'fc00::', 'fd00::',
        ]
        
        # Suspicious ports
        self.suspicious_ports = [
            21, 23, 135, 139, 445, 1433, 3306, 3389, 5432, 6379, 27017,
            4444, 5555, 6666, 31337
        ]
        
        self.logger.info("Initialized macOS native network tracker (lsof-based)")
    
    def collect(self) -> List[Dict]:
        """Collect network connections using lsof"""
        events = []
        
        try:
            # Use lsof to get all network connections
            # -i: network files only
            # -n: no DNS resolution (faster)
            # -P: no port name resolution (faster)
            cmd = ['lsof', '-i', '-n', '-P']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.logger.warning(f"lsof returned non-zero: {result.returncode}")
                return events
            
            # Parse lsof output
            for line in result.stdout.splitlines():
                try:
                    event = self._parse_lsof_line(line)
                    if event:
                        events.append(event)
                        
                        # Store in database
                        try:
                            self.db.insert_network_event(event)
                        except Exception as e:
                            self.logger.debug(f"Failed to insert network event: {e}")
                        
                        # Log high-threat connections
                        if event.get('threat_score', 0) > 70:
                            self.logger.warning(
                                f"High-threat connection: {event['process_name']} → "
                                f"{event['dest_ip']}:{event['dest_port']} "
                                f"Score: {event['threat_score']}"
                            )
                
                except Exception as e:
                    self.logger.debug(f"Error parsing lsof line: {e}")
                    continue
        
        except subprocess.TimeoutExpired:
            self.logger.error("lsof command timed out")
        except FileNotFoundError:
            self.logger.error("lsof command not found - install via 'brew install lsof'")
        except Exception as e:
            self.logger.error(f"Network collection error: {e}")
        
        return events
    
    def _parse_lsof_line(self, line: str) -> Optional[Dict]:
        """
        Parse a single line of lsof output
        
        Example lsof output:
        COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
        Google    12345  user   42u  IPv4 0x123456789      0t0  TCP 192.168.1.100:51234->142.250.185.46:443 (ESTABLISHED)
        """
        if not line or line.startswith('COMMAND'):
            return None
        
        parts = line.split()
        if len(parts) < 9:
            return None
        
        try:
            process_name = parts[0]
            pid = int(parts[1])
            connection_info = parts[-2]  # e.g., "192.168.1.100:51234->142.250.185.46:443"
            status = parts[-1].strip('()')  # e.g., "ESTABLISHED"
            
            # Parse connection string
            if '->' not in connection_info:
                return None  # Listening socket, skip
            
            local_addr, remote_addr = connection_info.split('->')
            
            # Parse local address
            if ':' in local_addr:
                local_ip, local_port = local_addr.rsplit(':', 1)
            else:
                return None
            
            # Parse remote address
            if ':' in remote_addr:
                remote_ip, remote_port = remote_addr.rsplit(':', 1)
            else:
                return None
            
            try:
                local_port = int(local_port)
                remote_port = int(remote_port)
            except ValueError:
                return None
            
            # Skip local/private IPs (except NAS)
            if self._is_safe_ip(remote_ip) and remote_ip != self.nas_ip:
                return None
            
            # Determine protocol from line
            protocol = 'TCP' if 'TCP' in line else 'UDP' if 'UDP' in line else 'UNKNOWN'
            
            # Calculate threat score
            threat_score = self._calculate_threat_score(
                remote_ip, remote_port, local_port, status, process_name
            )
            
            event = {
                'timestamp': time.time(),
                'source_ip': local_ip,
                'source_port': local_port,
                'dest_ip': remote_ip,
                'dest_port': remote_port,
                'protocol': protocol,
                'status': status,
                'process_name': process_name,
                'process_pid': pid,
                'country': 'Unknown',  # Could add geolocation lookup
                'city': 'Unknown',
                'latitude': 0.0,
                'longitude': 0.0,
                'threat_score': threat_score,
                'is_suspicious': threat_score > 50,
                'direction': 'outbound'
            }
            
            return event
        
        except (ValueError, IndexError) as e:
            return None
    
    def _is_safe_ip(self, ip: str) -> bool:
        """Check if IP is in safe/private range"""
        return any(ip.startswith(net) for net in self.safe_networks)
    
    def _calculate_threat_score(self, ip: str, remote_port: int, 
                                local_port: int, status: str, 
                                process_name: str) -> float:
        """Calculate threat score for connection"""
        score = 0.0
        
        # Suspicious ports
        if remote_port in self.suspicious_ports:
            score += 30
        if local_port in self.suspicious_ports:
            score += 20
        
        # Connection state
        if status in ['SYN_SENT', 'SYN_RECV']:
            score += 10
        
        # Suspicious process names
        suspicious_procs = ['nc', 'netcat', 'nmap', 'masscan', 'hping']
        if any(sus in process_name.lower() for sus in suspicious_procs):
            score += 40
        
        # Uncommon ports
        common_ports = [80, 443, 22, 25, 53, 110, 143, 993, 995]
        if remote_port not in common_ports and remote_port > 1024:
            score += 5
        
        return min(score, 100)
    
    def get_listening_ports(self) -> List[Dict]:
        """Get all listening ports using netstat"""
        listening = []
        
        try:
            cmd = ['netstat', '-an', '-p', 'tcp']
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.splitlines():
                if 'LISTEN' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        local_addr = parts[3]
                        if '.' in local_addr:
                            ip, port = local_addr.rsplit('.', 1)
                            try:
                                listening.append({
                                    'ip': ip,
                                    'port': int(port),
                                    'protocol': 'TCP'
                                })
                            except ValueError:
                                continue
        
        except Exception as e:
            self.logger.debug(f"Failed to get listening ports: {e}")
        
        return listening
    
    def get_connection_stats(self) -> Dict:
        """Get connection statistics"""
        try:
            cmd = ['netstat', '-s']
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            stats = {
                'tcp_connections': 0,
                'udp_datagrams': 0,
                'errors': 0
            }
            
            # Parse netstat -s output for statistics
            for line in result.stdout.splitlines():
                if 'connections established' in line.lower():
                    match = re.search(r'(\d+)', line)
                    if match:
                        stats['tcp_connections'] = int(match.group(1))
                elif 'datagrams sent' in line.lower():
                    match = re.search(r'(\d+)', line)
                    if match:
                        stats['udp_datagrams'] = int(match.group(1))
            
            return stats
        
        except Exception as e:
            self.logger.debug(f"Failed to get connection stats: {e}")
            return {}


def get_macos_native_tracker(config: dict, logger, db):
    """Factory function to create macOS native network tracker"""
    return MacOSNativeNetworkTracker(config, logger, db)
