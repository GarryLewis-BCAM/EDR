"""Process monitoring collector - Extracts 20+ behavioral features"""
import psutil
import time
import os
from typing import Dict, List, Optional
from collections import defaultdict


class ProcessMonitor:
    def __init__(self, config: dict, logger, db):
        self.config = config
        self.logger = logger
        self.db = db
        self.process_history = defaultdict(list)
        self.process_snapshots = {}  # Track last seen state for deduplication
        self.suspicious_names = config['collection']['process_monitor']['suspicious_names']
        self.whitelist = config['whitelist']['processes']
        
        # Phase 3: System daemon blacklist (benign background processes)
        self.daemon_blacklist = [
            'distnoted', 'trustd', 'cfprefsd', 'mdworker_shared', 'mds_stores',
            'com.apple.WebKit.Networking', 'com.apple.WebKit.WebContent',
            'MTLCompilerService', 'PlugInLibraryService', 'corespeechd',
            'diagnosticd', 'logd', 'syslogd', 'xpcproxy', 'securityd',
            'UserEventAgent', 'ContextStoreAgent', 'biomed', 'deleted',
            'rapportd', 'sharingd', 'bluetoothd', 'wifiFirmwareLoader',
            'iconservicesagent', 'iconservicesd', 'bird', 'cloudd'
        ]
        
    def collect(self) -> List[Dict]:
        """Collect all running processes with features"""
        events = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline',
                                            'cpu_percent', 'memory_info', 'num_threads',
                                            'create_time', 'ppid']):
                try:
                    pinfo = proc.info
                    
                    # Get connections separately (may fail with AccessDenied)
                    try:
                        pinfo['connections'] = proc.connections()
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pinfo['connections'] = []
                    
                    # Skip whitelisted processes
                    if pinfo['name'] in self.whitelist:
                        continue
                    
                    # Phase 3: Skip blacklisted system daemons (unless suspicious)
                    # We'll check suspicion score after feature extraction
                    is_blacklisted_daemon = pinfo['name'] in self.daemon_blacklist
                    
                    # Extract features
                    try:
                        features = self._extract_features(proc, pinfo)
                    except Exception as e:
                        self.logger.error(f"Feature extraction error for PID {pinfo['pid']}: {e}")
                        continue
                    
                    # Calculate suspicion score
                    suspicious_score = self._calculate_suspicion(features, pinfo)
                    
                    # Phase 3: Skip blacklisted daemons unless suspicious
                    if is_blacklisted_daemon and suspicious_score <= 30:
                        continue
                    
                    # Only include fields that ProcessEvent expects
                    event = {
                        'timestamp': time.time(),
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'cmdline': ' '.join(pinfo['cmdline']) if pinfo['cmdline'] else None,
                        'parent_pid': pinfo.get('ppid'),
                        'username': pinfo.get('username'),
                        'cpu_percent': features['cpu_percent'],
                        'memory_mb': features['memory_mb'],
                        'num_threads': pinfo.get('num_threads', 0),
                        'connections_count': features['connections_count'],
                        'suspicious_score': suspicious_score,
                        'features': features
                    }
                    
                    # Get parent process name
                    try:
                        parent = psutil.Process(pinfo['ppid'])
                        event['parent_name'] = parent.name()
                    except:
                        event['parent_name'] = None
                    
                    events.append(event)
                    
                    # Only store in database if changed or suspicious
                    should_log = self._should_log_process(pinfo['pid'], event, suspicious_score)
                    if should_log:
                        self.db.insert_process_event(event)
                    
                    # Track history
                    self.process_history[pinfo['pid']].append({
                        'timestamp': time.time(),
                        'cpu': features['cpu_percent'],
                        'memory': features['memory_mb']
                    })
                    
                    # Log suspicious processes
                    if suspicious_score > 50:
                        self.logger.warning(
                            f"Suspicious process detected: {pinfo['name']} "
                            f"(PID: {pinfo['pid']}, Score: {suspicious_score:.1f})",
                            pid=pinfo['pid'],
                            process_name=pinfo['name'],
                            score=suspicious_score
                        )
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            self.logger.error(f"Process collection error: {e}")
            
        return events
    
    def _extract_features(self, proc: psutil.Process, pinfo: Dict) -> Dict:
        """Extract 20+ behavioral features from process"""
        # Initialize with defaults for required fields
        features = {
            'cpu_percent': 0,
            'memory_mb': 0,
            'memory_percent': 0,
            'connections_count': 0,
            'num_threads': 0
        }
        
        try:
            # 1. CPU usage
            features['cpu_percent'] = pinfo.get('cpu_percent', 0) or 0
            
            # 2. Memory usage
            mem_info = pinfo.get('memory_info')
            features['memory_mb'] = mem_info.rss / (1024 * 1024) if mem_info else 0
            try:
                features['memory_percent'] = proc.memory_percent() if proc.is_running() else 0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                features['memory_percent'] = 0
            
            # 3. Process age
            create_time = pinfo.get('create_time', time.time())
            features['age_seconds'] = time.time() - create_time
            features['age_hours'] = features['age_seconds'] / 3600
            
            # 4. Thread count
            features['num_threads'] = pinfo.get('num_threads', 0)
            
            # 5. Connection count
            connections = pinfo.get('connections', [])
            features['connections_count'] = len(connections) if connections else 0
            features['has_network'] = features['connections_count'] > 0
            
            # 6. External connections
            features['external_connections'] = 0
            if connections:
                for conn in connections:
                    if conn.raddr and not self._is_local_ip(conn.raddr.ip):
                        features['external_connections'] += 1
            
            # 7. Command line characteristics
            cmdline = pinfo.get('cmdline', [])
            features['cmdline_length'] = len(' '.join(cmdline)) if cmdline else 0
            features['cmdline_args_count'] = len(cmdline) - 1 if cmdline else 0
            
            # 8. Suspicious command line patterns
            cmdline_str = ' '.join(cmdline).lower() if cmdline else ''
            features['has_suspicious_args'] = any(
                suspicious in cmdline_str 
                for suspicious in ['wget', 'curl', 'netcat', 'nc', 'bash -c', 'sh -c',
                                  'base64', 'eval', 'exec', 'powershell', '/bin/sh']
            )
            
            # 9. Process tree depth (estimate)
            features['process_tree_depth'] = self._get_tree_depth(pinfo['pid'])
            
            # 10. Is short-lived (< 5 minutes)
            features['is_short_lived'] = features['age_hours'] < 0.083  # 5 minutes
            
            # 11. High resource usage
            features['high_cpu'] = features['cpu_percent'] > 50
            features['high_memory'] = features['memory_mb'] > 500
            
            # 12. Has suspicious name (use word boundaries to avoid false positives)
            import re
            name = pinfo['name'].lower()
            features['suspicious_name'] = any(
                re.search(rf'\b{re.escape(suspicious)}\b', name) 
                for suspicious in self.suspicious_names
            )
            
            # 13. Unusual ports (if any connections)
            features['unusual_ports'] = []
            if connections:
                suspicious_ports = self.config['collection']['network_monitor']['suspicious_ports']
                for conn in connections:
                    if conn.laddr and conn.laddr.port in suspicious_ports:
                        features['unusual_ports'].append(conn.laddr.port)
                    if conn.raddr and conn.raddr.port in suspicious_ports:
                        features['unusual_ports'].append(conn.raddr.port)
            features['has_unusual_ports'] = len(features['unusual_ports']) > 0
            
            # 14. Process volatility (rapid CPU/memory changes)
            if pinfo['pid'] in self.process_history:
                history = self.process_history[pinfo['pid']][-10:]  # Last 10 samples
                if len(history) > 3:
                    cpu_values = [h['cpu'] for h in history]
                    cpu_std = self._std_dev(cpu_values)
                    features['cpu_volatility'] = cpu_std
                    features['high_volatility'] = cpu_std > 20
                else:
                    features['cpu_volatility'] = 0
                    features['high_volatility'] = False
            else:
                features['cpu_volatility'] = 0
                features['high_volatility'] = False
            
            # 15. Parent-child relationship anomalies
            features['unusual_parent'] = False
            if pinfo.get('ppid'):
                try:
                    parent = psutil.Process(pinfo['ppid'])
                    parent_name = parent.name().lower()
                    # Check for unusual parent-child combinations
                    if pinfo['name'].lower() in ['bash', 'sh', 'zsh'] and \
                       parent_name not in ['terminal', 'iterm', 'warp', 'launchd']:
                        features['unusual_parent'] = True
                except:
                    pass
            
            # 16. Username anomalies
            features['is_root'] = pinfo.get('username') == 'root'
            features['is_system'] = pinfo.get('username') in ['_system', 'daemon', 'nobody']
            
            # 17. File descriptors (if accessible)
            try:
                features['num_fds'] = proc.num_fds() if proc.is_running() else 0
                features['high_fd_count'] = features['num_fds'] > 100
            except:
                features['num_fds'] = 0
                features['high_fd_count'] = False
            
            # 18. I/O counters (if accessible)
            try:
                io_counters = proc.io_counters() if proc.is_running() else None
                if io_counters:
                    features['read_bytes'] = io_counters.read_bytes
                    features['write_bytes'] = io_counters.write_bytes
                    features['high_io'] = (io_counters.read_bytes + io_counters.write_bytes) > 100_000_000
                else:
                    features['read_bytes'] = 0
                    features['write_bytes'] = 0
                    features['high_io'] = False
            except:
                features['read_bytes'] = 0
                features['write_bytes'] = 0
                features['high_io'] = False
            
            # 19. Connection protocol distribution
            if connections:
                tcp_count = sum(1 for c in connections if c.type == 1)
                udp_count = sum(1 for c in connections if c.type == 2)
                features['tcp_connections'] = tcp_count
                features['udp_connections'] = udp_count
                features['connection_ratio'] = tcp_count / len(connections) if len(connections) > 0 else 0
            else:
                features['tcp_connections'] = 0
                features['udp_connections'] = 0
                features['connection_ratio'] = 0
            
            # 20. Process name length (very long names can be suspicious)
            features['name_length'] = len(pinfo['name'])
            features['long_name'] = features['name_length'] > 30
            
        except Exception as e:
            self.logger.error(f"Feature extraction error for PID {pinfo.get('pid')}: {e}")
        
        return features
    
    def _calculate_suspicion(self, features: Dict, pinfo: Dict) -> float:
        """Calculate suspicion score 0-100"""
        score = 0.0
        
        # Name-based scoring
        if features.get('suspicious_name', False):
            score += 40
        
        # Network-based scoring
        if features.get('external_connections', 0) > 5:
            score += 15
        if features.get('has_unusual_ports', False):
            score += 20
        
        # Resource-based scoring
        if features.get('high_cpu', False):
            score += 5
        if features.get('high_memory', False):
            score += 5
        if features.get('high_volatility', False):
            score += 10
        
        # Command line scoring
        if features.get('has_suspicious_args', False):
            score += 25
        if features.get('cmdline_length', 0) > 500:
            score += 10
        
        # Parent/user scoring
        if features.get('unusual_parent', False):
            score += 15
        if features.get('is_root', False) and pinfo['name'] not in ['kernel_task', 'launchd']:
            score += 10
        
        # Short-lived processes can be suspicious
        if features.get('is_short_lived', False) and features.get('has_network', False):
            score += 10
        
        return min(score, 100)  # Cap at 100
    
    def _is_local_ip(self, ip: str) -> bool:
        """Check if IP is local/private"""
        return ip.startswith(('127.', '192.168.', '10.', '172.'))
    
    def _get_tree_depth(self, pid: int) -> int:
        """Calculate process tree depth"""
        depth = 0
        current_pid = pid
        
        for _ in range(10):  # Limit to prevent infinite loops
            try:
                proc = psutil.Process(current_pid)
                parent = proc.ppid()
                if parent == 0 or parent == current_pid:
                    break
                current_pid = parent
                depth += 1
            except:
                break
        
        return depth
    
    def _std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _should_log_process(self, pid: int, event: Dict, suspicious_score: float) -> bool:
        """Determine if process should be logged (deduplication logic)"""
        # Always log suspicious processes
        if suspicious_score > 30:
            self.process_snapshots[pid] = event
            return True
        
        # Always log new processes
        if pid not in self.process_snapshots:
            self.process_snapshots[pid] = event
            return True
        
        # Check if process has changed significantly
        last_snapshot = self.process_snapshots[pid]
        
        # Check for significant resource changes (>20% CPU, >50MB memory)
        cpu_changed = abs(event['cpu_percent'] - last_snapshot.get('cpu_percent', 0)) > 20
        mem_changed = abs(event['memory_mb'] - last_snapshot.get('memory_mb', 0)) > 50
        
        # Check for network connection changes
        conn_changed = abs(event['connections_count'] - last_snapshot.get('connections_count', 0)) > 5
        
        # Check for command line changes
        cmdline_changed = event.get('cmdline') != last_snapshot.get('cmdline')
        
        if cpu_changed or mem_changed or conn_changed or cmdline_changed:
            self.process_snapshots[pid] = event
            return True
        
        # Log once every 10 minutes for long-running processes (heartbeat)
        time_since_last = event['timestamp'] - last_snapshot.get('timestamp', 0)
        if time_since_last > 600:  # 10 minutes
            self.process_snapshots[pid] = event
            return True
        
        # Otherwise, skip logging (no significant changes)
        return False
