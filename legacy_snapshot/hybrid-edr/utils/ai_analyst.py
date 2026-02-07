"""
AI Security Analyst
Analyzes threats, explains metrics, suggests remediations
"""
import json
import psutil
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class AISecurityAnalyst:
    """AI-powered security analyst for threat analysis and remediation"""
    
    def __init__(self, config: dict, logger, db):
        self.config = config
        self.logger = logger
        self.db = db
    
    def analyze_system_health(self, health_score: float, stats: Dict) -> Dict:
        """
        Analyze why system health is not 100% and provide fixes
        
        Returns:
            {
                'score': 89,
                'grade': 'B+',
                'issues': [
                    {
                        'severity': 'medium',
                        'title': 'High threat score detected',
                        'explanation': '...',
                        'fix': '...',
                        'auto_fixable': True,
                        'fix_command': 'sudo ...'
                    }
                ],
                'summary': 'Your system health is 89% because...'
            }
        """
        issues = []
        
        # Analyze threat score
        threat_score = stats.get('average_threat_score', 0)
        if threat_score > 20:
            suspicious_count = stats.get('suspicious_count', 0)
            total = stats.get('total_processes', 1)
            
            issues.append({
                'severity': 'high' if threat_score > 50 else 'medium',
                'title': f'Elevated threat level ({threat_score:.1f}/100)',
                'explanation': (
                    f"Your system has {suspicious_count} suspicious processes out of {total} total. "
                    f"This is causing the average threat score of {threat_score:.1f}. "
                    f"Common causes: malware, cryptocurrency miners, unauthorized remote access tools, "
                    f"or legitimate software behaving abnormally (high CPU/memory, unusual network activity)."
                ),
                'why': [
                    f"{suspicious_count} processes flagged as suspicious",
                    f"Average threat score: {threat_score:.1f}/100",
                    "May include false positives from system processes"
                ],
                'recommendations': [
                    "Review suspicious processes in the dashboard",
                    "Investigate high-threat processes (score >70)",
                    "Check if legitimate apps are consuming excessive resources",
                    "Run antivirus scan if threat score >60"
                ],
                'auto_fixable': False,
                'impact': 'High - System security and performance at risk'
            })
        
        # Analyze swap usage
        swap = psutil.swap_memory()
        if swap.percent > 80:
            memory = psutil.virtual_memory()
            
            issues.append({
                'severity': 'critical',
                'title': f'Swap memory critically high ({swap.percent:.1f}%)',
                'explanation': (
                    f"Your Mac is using {swap.used / (1024**3):.1f}GB of swap space (disk-based virtual memory). "
                    f"This means you've exhausted physical RAM ({memory.percent:.1f}% used) and macOS is "
                    f"paging memory to your SSD, causing severe slowdowns. "
                    f"This typically happens from memory leaks, too many apps open, or insufficient RAM for your workload."
                ),
                'why': [
                    f"Physical RAM: {memory.percent:.1f}% used ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)",
                    f"Swap: {swap.percent:.1f}% used ({swap.used / (1024**3):.1f}GB)",
                    "Memory leaks or too many apps running",
                    "SSD wear from constant paging"
                ],
                'recommendations': [
                    "Restart memory-heavy apps (Chrome, Warp, Docker)",
                    "Close unused applications",
                    "Restart your Mac to clear swap",
                    "Consider upgrading RAM if this happens frequently"
                ],
                'auto_fixable': True,
                'fix_actions': [
                    {
                        'label': 'Find memory hogs',
                        'action': 'identify_memory_leaks',
                        'safe': True
                    },
                    {
                        'label': 'Clear swap (requires restart)',
                        'action': 'clear_swap',
                        'safe': False,
                        'warning': 'This will restart your Mac'
                    }
                ],
                'impact': 'Critical - Severe performance degradation'
            })
        elif swap.percent > 50:
            issues.append({
                'severity': 'medium',
                'title': f'Swap memory elevated ({swap.percent:.1f}%)',
                'explanation': (
                    f"Swap usage at {swap.percent:.1f}% indicates you're running low on physical RAM. "
                    f"Not critical yet, but performance will degrade if this continues."
                ),
                'why': [
                    f"Swap: {swap.used / (1024**3):.1f}GB used",
                    "Multiple memory-intensive apps running"
                ],
                'recommendations': [
                    "Close unused apps",
                    "Restart memory-heavy applications"
                ],
                'auto_fixable': True,
                'fix_actions': [
                    {
                        'label': 'Show top memory users',
                        'action': 'show_memory_hogs',
                        'safe': True
                    }
                ],
                'impact': 'Medium - Performance slowdown likely'
            })
        
        # Analyze unresolved alerts
        unresolved = stats.get('unresolved_alerts', 0)
        if unresolved > 5:
            issues.append({
                'severity': 'medium',
                'title': f'{unresolved} unresolved security alerts',
                'explanation': (
                    f"You have {unresolved} security alerts that need investigation. "
                    f"These could be ongoing threats, policy violations, or false positives "
                    f"that should be marked as resolved."
                ),
                'why': [
                    f"{unresolved} alerts pending review",
                    "May include both real threats and false positives"
                ],
                'recommendations': [
                    "Review alerts in dashboard",
                    "Mark false positives as resolved",
                    "Investigate high-severity alerts immediately"
                ],
                'auto_fixable': False,
                'impact': 'Medium - Potential ongoing threats'
            })
        
        # Generate summary
        if not issues:
            summary = f"✅ System health is excellent at {health_score:.0f}%. No issues detected."
            grade = "A+"
        else:
            critical = sum(1 for i in issues if i['severity'] == 'critical')
            high = sum(1 for i in issues if i['severity'] == 'high')
            medium = sum(1 for i in issues if i['severity'] == 'medium')
            
            problem_desc = []
            if critical: problem_desc.append(f"{critical} critical issue{'s' if critical > 1 else ''}")
            if high: problem_desc.append(f"{high} high-severity issue{'s' if high > 1 else ''}")
            if medium: problem_desc.append(f"{medium} medium issue{'s' if medium > 1 else ''}")
            
            summary = (
                f"⚠️ System health is {health_score:.0f}% due to {', '.join(problem_desc)}. "
                f"Primary concerns: {issues[0]['title']}"
            )
            
            # Grading
            if health_score >= 95:
                grade = "A"
            elif health_score >= 85:
                grade = "B+"
            elif health_score >= 75:
                grade = "B"
            elif health_score >= 65:
                grade = "C+"
            else:
                grade = "D"
        
        return {
            'score': round(health_score),
            'grade': grade,
            'issues': issues,
            'summary': summary,
            'total_issues': len(issues),
            'critical_issues': sum(1 for i in issues if i['severity'] == 'critical'),
            'timestamp': datetime.now().isoformat()
        }
    
    def analyze_threat_level(self, threat_score: float, stats: Dict) -> Dict:
        """
        Explain why threat level is X and how to get to 0
        
        Returns:
            {
                'score': 10.5,
                'why_not_zero': '...',
                'top_threats': [...],
                'remediation': [...]
            }
        """
        
        if threat_score < 5:
            return {
                'score': threat_score,
                'status': 'excellent',
                'message': f"✅ Threat level is minimal at {threat_score:.1f}%. This is normal for a healthy system.",
                'explanation': "Low threat scores (0-5%) indicate mostly benign processes with normal behavior.",
                'why_not_zero': "Even clean systems show 0-5% due to system processes with unusual but legitimate behavior.",
                'action_needed': False
            }
        
        # Get actual suspicious processes
        suspicious_procs = self._get_suspicious_processes()
        
        top_threats = []
        for proc in suspicious_procs[:5]:  # Top 5
            top_threats.append({
                'name': proc['name'],
                'pid': proc['pid'],
                'score': proc['suspicious_score'],
                'why_suspicious': self._explain_process_threat(proc),
                'recommended_action': self._get_process_recommendation(proc)
            })
        
        why_explanations = []
        if suspicious_procs:
            why_explanations.append(
                f"{len(suspicious_procs)} processes exhibiting suspicious behavior"
            )
        
        # Analyze patterns
        high_cpu_count = sum(1 for p in suspicious_procs if p.get('cpu_percent', 0) > 70)
        if high_cpu_count > 0:
            why_explanations.append(
                f"{high_cpu_count} processes using excessive CPU (>70%)"
            )
        
        high_mem_count = sum(1 for p in suspicious_procs if p.get('memory_mb', 0) > 500)
        if high_mem_count > 0:
            why_explanations.append(
                f"{high_mem_count} processes using excessive memory (>500MB)"
            )
        
        return {
            'score': round(threat_score, 1),
            'status': 'elevated' if threat_score > 20 else 'moderate',
            'message': f"⚠️ Threat level at {threat_score:.1f}% - Investigation recommended",
            'why_not_zero': " and ".join(why_explanations) if why_explanations else "Unknown causes",
            'explanation': (
                f"A threat score of {threat_score:.1f}% indicates {len(suspicious_procs)} processes "
                f"with concerning behavior patterns. Ideal is 0-5%. Current level suggests "
                f"investigation needed."
            ),
            'top_threats': top_threats,
            'action_needed': True,
            'recommended_actions': [
                "Review top threats listed below",
                "Investigate processes with scores >70",
                "Consider killing suspicious processes",
                "Run malware scan if multiple unknowns detected"
            ]
        }
    
    def analyze_memory_issue(self) -> Dict:
        """Analyze memory usage and provide detailed fix suggestions"""
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Get top memory consumers
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'create_time']):
            try:
                pinfo = proc.info
                mem_mb = pinfo['memory_info'].rss / (1024 * 1024)
                if mem_mb > 100:  # Only processes using >100MB
                    age_hours = (datetime.now().timestamp() - pinfo['create_time']) / 3600
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'memory_mb': round(mem_mb, 1),
                        'age_hours': round(age_hours, 1)
                    })
            except:
                continue
        
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        top_10 = processes[:10]
        
        # Detect memory leaks (processes with high mem + old age)
        potential_leaks = [
            p for p in top_10 
            if p['memory_mb'] > 1000 and p['age_hours'] > 24
        ]
        
        analysis = {
            'memory_percent': memory.percent,
            'memory_used_gb': round(memory.used / (1024**3), 1),
            'memory_total_gb': round(memory.total / (1024**3), 1),
            'swap_percent': swap.percent,
            'swap_used_gb': round(swap.used / (1024**3), 1),
            'top_consumers': top_10,
            'potential_leaks': potential_leaks,
            'diagnosis': '',
            'recommendations': []
        }
        
        # Diagnosis
        if swap.percent > 80:
            analysis['diagnosis'] = (
                f"CRITICAL: Swap at {swap.percent:.0f}% - You've exhausted physical RAM "
                f"and are heavily paging to disk. This causes severe slowdowns."
            )
            analysis['recommendations'] = [
                {
                    'priority': 1,
                    'action': 'Restart these memory hogs immediately',
                    'targets': [p['name'] for p in top_10[:3]],
                    'expected_recovery': f"{sum(p['memory_mb'] for p in top_10[:3]) / 1024:.1f}GB"
                },
                {
                    'priority': 2,
                    'action': 'Restart your Mac to clear swap',
                    'command': 'sudo reboot',
                    'warning': 'Save all work first'
                }
            ]
        elif memory.percent > 85:
            analysis['diagnosis'] = (
                f"HIGH: RAM at {memory.percent:.0f}% - Close to exhaustion. "
                f"Will start swapping soon if not addressed."
            )
            analysis['recommendations'] = [
                {
                    'priority': 1,
                    'action': 'Close unused applications',
                    'targets': [p['name'] for p in top_10[3:6]]
                }
            ]
        else:
            analysis['diagnosis'] = f"NORMAL: Memory usage at {memory.percent:.0f}% is acceptable."
        
        return analysis
    
    def _get_suspicious_processes(self, limit: int = 10) -> List[Dict]:
        """Get most suspicious processes from database"""
        try:
            conn = self.db._get_connection()
            cursor = conn.execute('''
                SELECT pid, name, suspicious_score, cpu_percent, memory_mb, 
                       connections_count, timestamp
                FROM process_events
                WHERE suspicious_score > 30
                  AND timestamp > ?
                ORDER BY suspicious_score DESC, timestamp DESC
                LIMIT ?
            ''', (datetime.now().timestamp() - 86400, limit))  # Last 24 hours instead of 1 hour
            
            processes = []
            for row in cursor.fetchall():
                processes.append({
                    'pid': row[0],
                    'name': row[1],
                    'suspicious_score': row[2],
                    'cpu_percent': row[3],
                    'memory_mb': row[4],
                    'connections_count': row[5],
                    'timestamp': row[6]
                })
            
            return processes
        except Exception as e:
            self.logger.error(f"Failed to get suspicious processes: {e}")
            return []
    
    def _explain_process_threat(self, proc: Dict) -> str:
        """Explain why a process is flagged as suspicious"""
        reasons = []
        
        if proc['cpu_percent'] > 70:
            reasons.append(f"High CPU usage ({proc['cpu_percent']:.1f}%)")
        
        if proc['memory_mb'] > 500:
            reasons.append(f"High memory ({proc['memory_mb']:.0f}MB)")
        
        if proc['connections_count'] > 10:
            reasons.append(f"Many network connections ({proc['connections_count']})")
        
        if not reasons:
            reasons.append("Suspicious behavior patterns detected")
        
        return ", ".join(reasons)
    
    def _get_process_recommendation(self, proc: Dict) -> str:
        """Get recommended action for a suspicious process"""
        score = proc['suspicious_score']
        name = proc['name']
        
        # Known system processes
        known_safe = ['kernel_task', 'launchd', 'WindowServer', 'Finder']
        if name in known_safe:
            return "SAFE - System process, monitor only"
        
        if score > 80:
            return f"⚠️ HIGH RISK - Investigate immediately, consider killing process"
        elif score > 60:
            return "⚠️ MODERATE RISK - Investigate and monitor"
        else:
            return "ℹ️ LOW RISK - Monitor for now"
