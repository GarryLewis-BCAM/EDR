"""
Autonomous Threat Response Engine
- AI-powered decision making via Ollama
- Policy-based automatic response
- NAS protection and ransomware detection
- Process termination with verification
- Alert composition and delivery
"""
import os
import signal
import time
import psutil
import yaml
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

from utils.ai_threat_engine import get_ai_engine
from utils.db_v2 import EDRDatabase
from utils.alerting import AlertingSystem, Alert, AlertPriority

logger = logging.getLogger(__name__)


class ResponseEngine:
    """
    Autonomous threat response system with AI decision-making
    """
    
    def __init__(self, config_path: str, db: EDRDatabase, alerter: AlertingSystem):
        self.db = db
        self.alerter = alerter
        self.config = self._load_config(config_path)
        
        # Initialize AI engine
        ai_model = self.config.get('global', {}).get('ai_model', 'qwen2.5:14b')
        self.ai = get_ai_engine(model=ai_model)
        
        # Track active monitoring sessions
        self.monitoring_sessions = {}  # pid -> {start_time, check_count, incident_id}
        
        logger.info(f"Response engine initialized with AI model: {ai_model}")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load response policies from YAML"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def is_whitelisted(self, process_name: str) -> bool:
        """Check if process is whitelisted"""
        whitelist = self.config.get('whitelist', [])
        return process_name in whitelist
    
    def get_system_context(self) -> Dict:
        """Get current system context for AI decision-making"""
        try:
            stats = self.db.get_stats()
            active_incidents = self.db.get_active_incidents()
            
            # Check if user is active (keyboard/mouse activity)
            user_active = True  # Simplified - could check idle time
            
            return {
                'health_score': max(0, 100 - stats.get('average_threat_score', 0)),
                'active_threats': len(active_incidents),
                'user_active': user_active,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get system context: {e}")
            return {'health_score': 100, 'active_threats': 0, 'user_active': True}
    
    def evaluate_threat(self, process_data: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Evaluate if process is a threat using AI analysis
        
        Returns:
            (should_respond, ai_analysis)
        """
        # Skip whitelisted processes
        if self.is_whitelisted(process_data.get('name', '')):
            logger.debug(f"Process {process_data.get('name')} is whitelisted, skipping")
            return (False, None)
        
        # Get AI analysis
        try:
            ai_analysis = self.ai.analyze_threat(process_data)
            
            if not ai_analysis:
                logger.warning("AI analysis failed, skipping threat evaluation")
                return (False, None)
            
            threat_score = ai_analysis.get('threat_score', 0)
            thresholds = self.config.get('thresholds', {})
            
            # Determine if we should respond based on thresholds
            should_respond = threat_score >= thresholds.get('medium', 50)
            
            logger.info(
                f"AI evaluated {process_data.get('name')} (PID {process_data.get('pid')}): "
                f"score={threat_score}, type={ai_analysis.get('threat_type')}, "
                f"action={ai_analysis.get('recommended_action')}"
            )
            
            return (should_respond, ai_analysis)
            
        except Exception as e:
            logger.error(f"Failed to evaluate threat: {e}", exc_info=True)
            return (False, None)
    
    def decide_action(self, process_data: Dict, ai_analysis: Dict) -> Dict:
        """
        Decide what action to take using policy rules and AI
        
        Returns:
            Decision dict with action, reason, etc.
        """
        threat_score = ai_analysis.get('threat_score', 0)
        threat_type = ai_analysis.get('threat_type', 'unknown')
        thresholds = self.config.get('thresholds', {})
        
        # Check if AI decisions are enabled
        enable_ai_decisions = self.config.get('global', {}).get('enable_ai_decisions', True)
        
        # Critical threats: auto-kill (unless AI overrides)
        if threat_score >= thresholds.get('critical', 85):
            rule = self._find_matching_rule('critical_threat_auto_kill')
            
            if enable_ai_decisions and rule and rule.get('ai_override'):
                # Let AI decide if we should override auto-kill
                system_context = self.get_system_context()
                threat_data = {**process_data, **ai_analysis}
                ai_decision = self.ai.decide_action(threat_data, system_context)
                
                if ai_decision and ai_decision.get('action') != 'kill_now':
                    logger.info(f"AI overrode auto-kill for {process_data.get('name')}: {ai_decision.get('reason')}")
                    return ai_decision
            
            return {
                'action': 'kill_now',
                'confidence': 'high',
                'reason': f'Critical threat detected: score {threat_score}/100',
                'user_message': f"Critical threat {process_data.get('name')} blocked automatically",
                'escalate': True
            }
        
        # High threats: AI decides
        elif threat_score >= thresholds.get('high', 70):
            if enable_ai_decisions:
                system_context = self.get_system_context()
                threat_data = {**process_data, **ai_analysis}
                return self.ai.decide_action(threat_data, system_context)
            else:
                return {
                    'action': 'alert_user',
                    'confidence': 'medium',
                    'reason': 'High threat score, alerting user',
                    'user_message': f"High-threat process detected: {process_data.get('name')}"
                }
        
        # Medium threats: monitor
        elif threat_score >= thresholds.get('medium', 50):
            return {
                'action': 'monitor_closely',
                'confidence': 'medium',
                'reason': 'Suspicious activity, monitoring for escalation',
                'user_message': f"Monitoring suspicious process: {process_data.get('name')}"
            }
        
        # Low threats: log only
        else:
            return {
                'action': 'log_only',
                'confidence': 'low',
                'reason': 'Low threat score, logging for analysis',
                'user_message': None
            }
    
    def _find_matching_rule(self, rule_name: str) -> Optional[Dict]:
        """Find a rule by name in config"""
        rules = self.config.get('rules', [])
        for rule in rules:
            if rule.get('name') == rule_name:
                return rule
        return None
    
    def execute_action(self, action_decision: Dict, process_data: Dict, incident_id: str) -> Tuple[bool, str]:
        """
        Execute the decided action
        
        Returns:
            (success, result_message)
        """
        action = action_decision.get('action')
        pid = process_data.get('pid')
        name = process_data.get('name')
        
        dry_run = self.config.get('global', {}).get('dry_run', False)
        
        try:
            if action == 'kill_now':
                return self._kill_process(pid, name, dry_run)
            
            elif action == 'monitor_closely':
                return self._start_monitoring(pid, name, incident_id)
            
            elif action == 'alert_user':
                return self._send_alert(action_decision, process_data, incident_id)
            
            elif action == 'block_network':
                return self._block_network(pid, name, dry_run)
            
            elif action == 'quarantine':
                return (False, "Quarantine not yet implemented")
            
            elif action == 'log_only':
                return (True, "Logged")
            
            else:
                logger.warning(f"Unknown action: {action}")
                return (False, f"Unknown action: {action}")
                
        except Exception as e:
            logger.error(f"Failed to execute action {action}: {e}", exc_info=True)
            return (False, str(e))
    
    def _kill_process(self, pid: int, name: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Kill a process with verification"""
        try:
            if dry_run:
                logger.info(f"[DRY RUN] Would kill process {name} (PID {pid})")
                return (True, "Dry run - process would be killed")
            
            # Check if process still exists
            try:
                proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return (False, "Process no longer exists")
            
            # Verify it's the same process
            if proc.name() != name:
                return (False, f"Process name mismatch: expected {name}, got {proc.name()}")
            
            # Kill the process
            os.kill(pid, signal.SIGKILL)
            
            # Verify it's dead
            time.sleep(0.5)
            if psutil.pid_exists(pid):
                # Try again
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)
                
                if psutil.pid_exists(pid):
                    return (False, "Process survived SIGKILL")
            
            logger.info(f"Successfully killed process {name} (PID {pid})")
            return (True, "Process terminated successfully")
            
        except ProcessLookupError:
            return (True, "Process already terminated")
        except PermissionError:
            return (False, "Permission denied - requires elevated privileges")
        except Exception as e:
            return (False, f"Failed to kill process: {str(e)}")
    
    def _start_monitoring(self, pid: int, name: str, incident_id: str) -> Tuple[bool, str]:
        """Start close monitoring of a suspicious process"""
        self.monitoring_sessions[pid] = {
            'start_time': time.time(),
            'check_count': 0,
            'incident_id': incident_id,
            'name': name
        }
        logger.info(f"Started monitoring {name} (PID {pid})")
        return (True, f"Monitoring started for {name}")
    
    def _send_alert(self, decision: Dict, process_data: Dict, incident_id: str) -> Tuple[bool, str]:
        """Send alert to user via configured channels"""
        try:
            # Compose AI-generated alert message
            incident_data = {
                'action': decision.get('action'),
                'process_name': process_data.get('name'),
                'pid': process_data.get('pid'),
                'threat_score': process_data.get('threat_score', 0),
                'threat_type': process_data.get('threat_type', 'unknown'),
                'reasoning': decision.get('reason', 'Suspicious activity detected')
            }
            
            ai_compose = self.config.get('actions', {}).get('send_alert', {}).get('ai_compose', True)
            
            if ai_compose:
                message = self.ai.compose_alert(incident_data)
            else:
                message = decision.get('user_message', f"Threat detected: {process_data.get('name')}")
            
            # Send via alerting system
            alert = Alert(
                title="Threat Detected" if not decision.get('escalate') else "Critical Threat Blocked",
                message=message,
                priority=AlertPriority.CRITICAL if decision.get('escalate') else AlertPriority.HIGH,
                severity='critical' if decision.get('escalate') else 'high',
                source='AI_ResponseEngine',
                details=incident_data
            )
            self.alerter.send_alert(alert)
            
            logger.info(f"Sent alert for incident {incident_id}")
            return (True, "Alert sent")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return (False, f"Alert failed: {str(e)}")
    
    def _block_network(self, pid: int, name: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Block network access for a process (macOS)"""
        # This would require firewall rules or Little Snitch API
        # Simplified: just log for now
        logger.warning(f"Network blocking requested for {name} (PID {pid}) - not yet implemented")
        return (False, "Network blocking not yet implemented")
    
    def verify_action(self, action: str, pid: int, name: str) -> bool:
        """Verify that an action was successful"""
        if action == 'kill_now':
            # Check if process is dead
            return not psutil.pid_exists(pid)
        
        elif action == 'monitor_closely':
            # Check if we're still monitoring
            return pid in self.monitoring_sessions
        
        elif action in ['alert_user', 'log_only']:
            # These always succeed if executed
            return True
        
        return False
    
    def check_nas_activity(self, process_data: Dict) -> Optional[Dict]:
        """
        Check if process is accessing NAS and analyze for threats
        
        Returns:
            NAS analysis dict if suspicious, None otherwise
        """
        nas_config = self.config.get('nas_protection', {})
        if not nas_config.get('enabled'):
            return None
        
        nas_ip = nas_config.get('nas_ip', '192.168.1.80')
        
        # Check if process has connections to NAS
        pid = process_data.get('pid')
        try:
            proc = psutil.Process(pid)
            connections = proc.connections()
            
            nas_connections = [
                conn for conn in connections
                if conn.raddr and conn.raddr.ip == nas_ip
            ]
            
            if not nas_connections:
                return None
            
            # Check for open files on NAS mounts
            open_files = []
            mount_points = nas_config.get('mount_points', [])
            for mount in mount_points:
                try:
                    files = [f.path for f in proc.open_files() if f.path.startswith(mount)]
                    open_files.extend(files)
                except:
                    pass
            
            if not open_files and not nas_connections:
                return None
            
            # Build activity data for AI analysis
            activity_data = {
                'nas_ip': nas_ip,
                'process_name': process_data.get('name'),
                'file_count': len(open_files),
                'write_ops': 0,  # Would need monitoring to track
                'read_ops': 0,
                'file_types': list(set([Path(f).suffix for f in open_files])),
                'pattern': 'unknown',
                'time_window': '5 seconds'
            }
            
            # Get AI analysis of NAS activity
            nas_analysis = self.ai.analyze_nas_activity(activity_data)
            
            if nas_analysis.get('is_suspicious'):
                logger.warning(
                    f"Suspicious NAS activity detected: {process_data.get('name')} - "
                    f"{nas_analysis.get('likely_attack')}"
                )
                return nas_analysis
            
            return None
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
        except Exception as e:
            logger.error(f"Failed to check NAS activity: {e}")
            return None
    
    def handle_threat(self, process_data: Dict) -> Optional[str]:
        """
        Main threat handling workflow
        
        Returns:
            incident_id if threat was handled, None otherwise
        """
        # Evaluate threat with AI
        should_respond, ai_analysis = self.evaluate_threat(process_data)
        
        if not should_respond:
            return None
        
        # Check for NAS activity
        nas_analysis = self.check_nas_activity(process_data)
        if nas_analysis and nas_analysis.get('threat_level') in ['high', 'critical']:
            logger.critical(f"NAS threat detected: {nas_analysis.get('likely_attack')}")
            # Upgrade threat score
            ai_analysis['threat_score'] = max(ai_analysis.get('threat_score', 0), 90)
            ai_analysis['threat_type'] = nas_analysis.get('likely_attack', 'ransomware')
            ai_analysis['nas_activity'] = True
        
        # Create incident record
        incident_data = {
            'process_name': process_data.get('name'),
            'process_pid': process_data.get('pid'),
            'threat_score': ai_analysis.get('threat_score', 0),
            'threat_type': ai_analysis.get('threat_type', 'unknown'),
            'ai_analyzed': ai_analysis.get('ai_analyzed', False),
            'ai_model': ai_analysis.get('model'),
            'ai_confidence': ai_analysis.get('confidence'),
            'ai_reasoning': ai_analysis.get('reasoning'),
            'recommended_action': ai_analysis.get('recommended_action'),
            'nas_activity': nas_analysis is not None
        }
        
        incident_id = self.db.create_threat_incident(incident_data)
        if not incident_id:
            logger.error("Failed to create incident record")
            return None
        
        # Update incident status to analyzing
        self.db.update_incident_status(incident_id, 'analyzing', 'AI analyzing threat')
        
        # Decide action
        action_decision = self.decide_action(process_data, ai_analysis)
        
        # Execute action
        success, result = self.execute_action(action_decision, process_data, incident_id)
        
        # Record action in database
        action = action_decision.get('action')
        self.db.record_incident_action(incident_id, action, result if success else f"FAILED: {result}")
        
        # Verify action
        if success and action != 'monitor_closely':
            time.sleep(1)  # Wait for action to take effect
            verified = self.verify_action(action, process_data.get('pid'), process_data.get('name'))
            self.db.verify_incident_resolution(incident_id, verified)
            
            if not verified:
                logger.error(f"Action verification failed for incident {incident_id}")
                # Send critical alert
                alert = Alert(
                    title="Threat Elimination Failed",
                    message=f"⚠️ CRITICAL: Failed to eliminate threat {process_data.get('name')}. Manual intervention required!",
                    priority=AlertPriority.CRITICAL,
                    severity='critical',
                    source='AI_ResponseEngine',
                    details={'incident_id': incident_id, 'pid': process_data.get('pid')}
                )
                self.alerter.send_alert(alert)
        
        # Perform post-incident analysis if threat was killed
        if action == 'kill_now' and success:
            try:
                post_analysis = self.ai.post_incident_analysis({
                    'process_name': process_data.get('name'),
                    'action': action,
                    'threat_score': ai_analysis.get('threat_score'),
                    'threat_type': ai_analysis.get('threat_type'),
                    'timeline': []  # Would include full timeline
                })
                self.db.close_incident(incident_id, post_analysis)
            except Exception as e:
                logger.error(f"Failed to perform post-incident analysis: {e}")
        
        logger.info(f"Handled threat {process_data.get('name')} - incident {incident_id}, action: {action}, result: {result}")
        
        return incident_id
    
    def check_monitored_processes(self):
        """Check all processes under active monitoring for escalation"""
        for pid, session in list(self.monitoring_sessions.items()):
            try:
                # Check if process still exists
                if not psutil.pid_exists(pid):
                    logger.info(f"Monitored process {session['name']} (PID {pid}) terminated")
                    del self.monitoring_sessions[pid]
                    continue
                
                # Get current process data
                proc = psutil.Process(pid)
                process_data = {
                    'pid': pid,
                    'name': proc.name(),
                    'cpu_percent': proc.cpu_percent(interval=0.1),
                    'memory_mb': proc.memory_info().rss / (1024 * 1024),
                    'num_connections': len(proc.connections()),
                    'cmdline': ' '.join(proc.cmdline())
                }
                
                # Re-evaluate with AI
                _, ai_analysis = self.evaluate_threat(process_data)
                
                if ai_analysis and ai_analysis.get('threat_score', 0) >= 80:
                    logger.warning(f"Monitored process {session['name']} escalated to high threat")
                    
                    # Update incident and take action
                    self.db.update_incident_status(
                        session['incident_id'],
                        'monitoring',
                        f"Threat escalated to {ai_analysis.get('threat_score')}/100"
                    )
                    
                    # Execute kill action
                    success, result = self._kill_process(pid, session['name'])
                    self.db.record_incident_action(session['incident_id'], 'kill_now', result)
                    
                    # Remove from monitoring
                    del self.monitoring_sessions[pid]
                
                # Check timeout
                session['check_count'] += 1
                monitor_config = self.config.get('actions', {}).get('monitor_closely', {})
                max_duration = monitor_config.get('duration', 60)
                
                if time.time() - session['start_time'] > max_duration:
                    logger.info(f"Monitoring timeout for {session['name']} (PID {pid})")
                    self.db.update_incident_status(
                        session['incident_id'],
                        'closed',
                        'Monitoring period completed, no escalation'
                    )
                    del self.monitoring_sessions[pid]
                    
            except Exception as e:
                logger.error(f"Error checking monitored process {pid}: {e}")
                if pid in self.monitoring_sessions:
                    del self.monitoring_sessions[pid]


def get_response_engine(db: EDRDatabase, alerter: AlertingSystem) -> ResponseEngine:
    """Factory function to create response engine"""
    config_path = Path(__file__).parent.parent / 'config' / 'response_policies.yaml'
    return ResponseEngine(str(config_path), db, alerter)
