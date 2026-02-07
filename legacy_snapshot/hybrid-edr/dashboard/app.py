"""
Production-grade EDR Dashboard
- Flask-based web interface
- RESTful API
- Real-time metrics
- Alert management
- System health monitoring
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import yaml
import json

from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db_v2 import EDRDatabase, DatabaseError
from utils.ai_analyst import AISecurityAnalyst


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DashboardApp:
    """Production-grade EDR dashboard application"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.app = Flask(__name__,
                        static_folder='static',
                        template_folder='templates')
        
        # Enable CORS for API access
        CORS(self.app)
        
        # Initialize SocketIO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # Initialize database connection
        try:
            self.db = EDRDatabase(
                db_path=self.config['paths']['database'],
                nas_backup_path=self.config['paths'].get('nas_backups')
            )
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
        
        # Initialize AI analyst
        self.ai_analyst = AISecurityAnalyst(self.config, logger, self.db)
        
        # Register routes
        self._register_routes()
        self._register_socketio_events()
        
        # Configure app
        self.app.config['SECRET_KEY'] = os.urandom(24)
        self.app.config['JSON_SORT_KEYS'] = False
        
        # NAS IP from config for service labeling
        self.nas_ip = self.config.get('nas', {}).get('ip', '192.168.1.80')
        
        # Device name mapping
        self.device_names = {
            self.nas_ip: 'NAS (Synology DS225+)',
            '192.168.1.93': self.config['system'].get('hostname', 'MacBook'),
            '127.0.0.1': 'localhost',
            '::1': 'localhost'
        }
        
        # Production-grade security headers
        @self.app.after_request
        def add_security_headers(response):
            """Add security headers to all responses"""
            # HTTPS enforcement
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            # XSS protection
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            # Content Security Policy - Allow CDN resources for dashboard
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com https://cdn.socket.io; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://unpkg.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'"
            )
            # Referrer policy
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            # Permissions policy
            response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
            
            # CACHE CONTROL: Prevent browser from caching HTML/JS/CSS
            # This prevents the network map issue from happening again
            if response.content_type and any(ct in response.content_type for ct in ['text/html', 'application/javascript', 'text/css']):
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            
            return response
        
    def _load_config(self, config_path: str) -> Dict:
        """Load and validate configuration"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate required keys
            required = ['paths', 'system']
            for key in required:
                if key not in config:
                    raise ValueError(f"Missing required config key: {key}")
            
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _get_device_name(self, ip: str) -> str:
        """Get human-readable device name for IP address"""
        return self.device_names.get(ip, ip)
    
    def _get_service_name(self, ip: str, port: int) -> str:
        """Get human-readable service name for port/IP combination"""
        # NAS-specific services
        if ip == self.nas_ip:
            nas_ports = {
                5000: 'DSM (HTTP)',
                5001: 'DSM (HTTPS)',
                5005: 'DSM Admin (HTTP)',
                5006: 'DSM Admin (HTTPS)',
                6690: 'Cloud Sync',
                873: 'rsync',
                3000: 'Container Manager',
                7000: 'Docker Registry',
                9117: 'Drive Server'
            }
            if port in nas_ports:
                return nas_ports[port]
        
        # Common services
        common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
            53: 'DNS', 80: 'HTTP', 110: 'POP3', 143: 'IMAP',
            443: 'HTTPS', 445: 'SMB', 993: 'IMAP/S', 995: 'POP3/S',
            3306: 'MySQL', 3389: 'RDP', 5432: 'PostgreSQL',
            6379: 'Redis', 8080: 'HTTP-Alt', 27017: 'MongoDB',
            5228: 'Google Services', 587: 'SMTP (TLS)'
        }
        return common_ports.get(port, f'Port {port}')
    
    def _register_routes(self):
        """Register all routes"""
        
        # ============= WEB PAGES =============
        
        @self.app.route('/')
        def index():
            """Main dashboard page - Cyberpunk SOC Dashboard"""
            try:
                return render_template('unified_dashboard_v2.html',
                                     system_name=self.config['system']['name'])
            except Exception as e:
                logger.error(f"Error rendering dashboard: {e}")
                return f"Dashboard error: {e}", 500
        
        @self.app.route('/alerts')
        def alerts_page():
            """Alerts management page"""
            return render_template('alerts.html',
                                 system_name=self.config['system']['name'])
        
        @self.app.route('/processes')
        def processes_page():
            """Process monitoring page"""
            return render_template('processes.html',
                                 system_name=self.config['system']['name'])
        
        @self.app.route('/health')
        def health_page():
            """System health page"""
            return render_template('health.html',
                                 system_name=self.config['system']['name'])
        
        @self.app.route('/network')
        def network_page():
            """Network connections page"""
            return render_template('network.html',
                                 system_name=self.config['system']['name'])
        
        @self.app.route('/ml')
        def ml_page():
            """ML training page"""
            return render_template('ml_training.html',
                                 system_name=self.config['system']['name'])
        
        # ============= API ENDPOINTS =============
        
        @self.app.route('/api/stats')
        def api_stats():
            """Get system statistics"""
            try:
                stats = self.db.get_stats()
                stats['timestamp'] = datetime.now().isoformat()
                stats['uptime'] = self._get_uptime()
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/collector/status')
        def api_collector_status():
            """Get collector status (is it running?)"""
            try:
                conn = self.db._get_connection()
                
                # Check if we've received events recently (last 60 seconds - allows for 30s collection interval + buffer)
                cutoff = datetime.now().timestamp() - 60
                cursor = conn.execute(
                    'SELECT COUNT(*) as count, MAX(timestamp) as last_event FROM process_events WHERE timestamp > ?',
                    (cutoff,)
                )
                row = cursor.fetchone()
                
                is_running = row['count'] > 0 if row else False
                last_event = row['last_event'] if row and row['last_event'] else None
                
                # Get collector info from database stats
                stats = self.db.get_stats()
                
                return jsonify({
                    'running': is_running,
                    'last_activity': datetime.fromtimestamp(last_event).isoformat() if last_event else None,
                    'seconds_since_activity': (datetime.now().timestamp() - last_event) if last_event else None,
                    'total_events': stats.get('total_processes', 0),
                    'status': 'active' if is_running else 'inactive'
                })
            except Exception as e:
                logger.error(f"Error getting collector status: {e}")
                return jsonify({'running': False, 'status': 'error', 'error': str(e)}), 500
        
        @self.app.route('/api/incidents')
        def api_incidents():
            """Get threat incidents with timeline"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                status = request.args.get('status', default=None, type=str)
                
                if status:
                    # Get incidents by status
                    if status == 'active':
                        incidents = self.db.get_active_incidents()
                    else:
                        conn = self.db._get_connection()
                        cutoff = datetime.now().timestamp() - (hours * 3600)
                        cursor = conn.execute(
                            'SELECT * FROM threat_incidents WHERE status = ? AND timestamp > ? ORDER BY timestamp DESC',
                            (status, cutoff)
                        )
                        incidents = [dict(row) for row in cursor.fetchall()]
                else:
                    # Get all recent incidents
                    incidents = self.db.get_incident_history(hours)
                
                # Parse JSON fields
                for incident in incidents:
                    if incident.get('timeline'):
                        try:
                            incident['timeline'] = json.loads(incident['timeline'])
                        except:
                            pass
                    if incident.get('post_incident_analysis'):
                        try:
                            incident['post_incident_analysis'] = json.loads(incident['post_incident_analysis'])
                        except:
                            pass
                
                return jsonify({
                    'count': len(incidents),
                    'incidents': incidents
                })
            except Exception as e:
                logger.error(f"Error getting incidents: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/alerts')
        def api_alerts():
            """Get recent alerts"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                unresolved_only = request.args.get('unresolved', default='false').lower() == 'true'
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                query = 'SELECT * FROM alerts WHERE timestamp > ?'
                params = [cutoff]
                
                if unresolved_only:
                    query += ' AND resolved = 0'
                
                query += ' ORDER BY timestamp DESC LIMIT 100'
                
                cursor = conn.execute(query, params)
                alerts = [dict(row) for row in cursor.fetchall()]
                
                # Parse JSON fields
                for alert in alerts:
                    if alert.get('details'):
                        try:
                            alert['details'] = json.loads(alert['details'])
                        except:
                            pass
                    if alert.get('response_actions'):
                        try:
                            alert['response_actions'] = json.loads(alert['response_actions'])
                        except:
                            pass
                
                return jsonify({
                    'count': len(alerts),
                    'alerts': alerts
                })
            except Exception as e:
                logger.error(f"Error getting alerts: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
        def api_resolve_alert(alert_id: int):
            """Mark alert as resolved"""
            try:
                conn = self.db._get_connection()
                
                # Get feedback from request
                data = request.get_json() or {}
                feedback = data.get('feedback', '')
                is_false_positive = data.get('false_positive', False)
                
                conn.execute('''
                    UPDATE alerts 
                    SET resolved = 1, 
                        user_feedback = ?,
                        false_positive = ?
                    WHERE id = ?
                ''', (feedback, 1 if is_false_positive else 0, alert_id))
                
                return jsonify({'success': True, 'message': 'Alert resolved'})
            except Exception as e:
                logger.error(f"Error resolving alert: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/processes/recent')
        def api_recent_processes():
            """Get recent process events"""
            try:
                minutes = request.args.get('minutes', default=60, type=int)
                suspicious_only = request.args.get('suspicious', default='false').lower() == 'true'
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (minutes * 60)
                
                query = '''
                    SELECT pid, name, cmdline, username, cpu_percent, memory_mb, 
                           suspicious_score, timestamp
                    FROM process_events 
                    WHERE timestamp > ?
                '''
                params = [cutoff]
                
                if suspicious_only:
                    query += ' AND suspicious_score > 50'
                
                query += ' ORDER BY suspicious_score DESC, timestamp DESC LIMIT 50'
                
                cursor = conn.execute(query, params)
                processes = [dict(row) for row in cursor.fetchall()]
                
                return jsonify({
                    'count': len(processes),
                    'processes': processes
                })
            except Exception as e:
                logger.error(f"Error getting processes: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/processes/top')
        def api_top_processes():
            """Get top processes by resource usage"""
            try:
                metric = request.args.get('metric', default='cpu', type=str)
                limit = request.args.get('limit', default=10, type=int)
                
                if metric not in ['cpu', 'memory', 'suspicious']:
                    return jsonify({'error': 'Invalid metric'}), 400
                
                column_map = {
                    'cpu': 'cpu_percent',
                    'memory': 'memory_mb',
                    'suspicious': 'suspicious_score'
                }
                
                conn = self.db._get_connection()
                
                # Get latest snapshot (last 5 minutes)
                cutoff = datetime.now().timestamp() - 300
                
                query = f'''
                    SELECT pid, name, username, cpu_percent, memory_mb, 
                           suspicious_score, timestamp
                    FROM process_events 
                    WHERE timestamp > ?
                    ORDER BY {column_map[metric]} DESC
                    LIMIT ?
                '''
                
                cursor = conn.execute(query, (cutoff, limit))
                processes = [dict(row) for row in cursor.fetchall()]
                
                return jsonify({
                    'metric': metric,
                    'count': len(processes),
                    'processes': processes
                })
            except Exception as e:
                logger.error(f"Error getting top processes: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/files/suspicious')
        def api_suspicious_files():
            """Get suspicious file activity"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                cursor = conn.execute('''
                    SELECT event_type, path, process_name, timestamp
                    FROM file_events
                    WHERE is_suspicious = 1 AND timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                ''', (cutoff,))
                
                files = [dict(row) for row in cursor.fetchall()]
                
                return jsonify({
                    'count': len(files),
                    'files': files
                })
            except Exception as e:
                logger.error(f"Error getting suspicious files: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/ai/analyze')
        def api_ai_analyze():
            """Get AI analysis of system health and threats"""
            try:
                stats = self.db.get_stats()
                
                # Calculate health score
                health_score = max(0, 100 - stats.get('average_threat_score', 0))
                
                # Get AI analysis
                health_analysis = self.ai_analyst.analyze_system_health(health_score, stats)
                threat_analysis = self.ai_analyst.analyze_threat_level(
                    stats.get('average_threat_score', 0), 
                    stats
                )
                memory_analysis = self.ai_analyst.analyze_memory_issue()
                
                return jsonify({
                    'health': health_analysis,
                    'threats': threat_analysis,
                    'memory': memory_analysis,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"AI analysis error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/threats/map')
        def api_threats_map():
            """Get threat data for world map visualization"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                # Get suspicious network connections with geolocation
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
                        'country': row[2] or 'Unknown',
                        'city': row[3] or 'Unknown',
                        'lat': row[4] or 0,
                        'lon': row[5] or 0,
                        'process': row[6],
                        'threat_score': row[7],
                        'count': row[8],
                        'last_seen': row[9]
                    })
                
                return jsonify({
                    'threats': threats,
                    'count': len(threats),
                    'timeframe_hours': hours
                })
            except Exception as e:
                logger.error(f"Error getting threat map data: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/processes/active')
        def api_active_suspicious():
            """Get currently running suspicious processes"""
            try:
                import psutil
                active_suspicious = []
                
                # Get list of all running PIDs
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                    try:
                        pinfo = proc.info
                        
                        # Query database for this process's threat score
                        conn = self.db._get_connection()
                        cursor = conn.execute('''
                            SELECT suspicious_score, timestamp
                            FROM process_events
                            WHERE pid = ? AND suspicious_score > 50
                            ORDER BY timestamp DESC
                            LIMIT 1
                        ''', (pinfo['pid'],))
                        
                        row = cursor.fetchone()
                        if row:
                            active_suspicious.append({
                                'pid': pinfo['pid'],
                                'name': pinfo['name'],
                                'cpu_percent': pinfo['cpu_percent'] or 0,
                                'memory_mb': pinfo['memory_info'].rss / (1024 * 1024) if pinfo['memory_info'] else 0,
                                'suspicious_score': row[0],
                                'last_seen': row[1]
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Sort by threat score
                active_suspicious.sort(key=lambda x: x['suspicious_score'], reverse=True)
                
                return jsonify({
                    'count': len(active_suspicious),
                    'processes': active_suspicious[:20]  # Top 20
                })
                
            except Exception as e:
                logger.error(f"Error getting active suspicious processes: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/process/kill/<int:pid>', methods=['POST'])
        def api_kill_process(pid: int):
            """Kill a process by PID"""
            try:
                data = request.get_json() or {}
                process_name = data.get('name', 'unknown')
                
                # Security check - don't allow killing critical processes
                critical_processes = ['kernel_task', 'launchd', 'WindowServer', 'loginwindow', 'systemd']
                if process_name.lower() in [p.lower() for p in critical_processes]:
                    return jsonify({
                        'error': f'Cannot kill critical system process: {process_name}'
                    }), 403
                
                # Kill the process
                import psutil
                try:
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                    proc.kill()  # SIGKILL
                    
                    logger.warning(f"Process killed via dashboard: {proc_name} (PID: {pid})")
                    
                    return jsonify({
                        'success': True,
                        'message': f'Process {proc_name} (PID: {pid}) terminated',
                        'pid': pid,
                        'name': proc_name
                    })
                except psutil.NoSuchProcess:
                    return jsonify({'error': f'Process {pid} not found'}), 404
                except psutil.AccessDenied:
                    return jsonify({'error': f'Access denied - try running as admin'}), 403
                
            except Exception as e:
                logger.error(f"Error killing process: {e}")
                return jsonify({'error': str(e)}), 500
        
        # ============= NETWORK API ENDPOINTS =============
        
        @self.app.route('/api/network/connections')
        def api_network_connections():
            """Get network connections"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                suspicious_only = request.args.get('suspicious', default='false').lower() == 'true'
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                query = '''
                    SELECT dest_ip, dest_port, protocol, process_name, process_pid,
                           country, city, threat_score, timestamp, status
                    FROM network_events
                    WHERE timestamp > ?
                '''
                params = [cutoff]
                
                if suspicious_only:
                    query += ' AND is_suspicious = 1'
                
                query += ' ORDER BY timestamp DESC LIMIT 500'
                
                cursor = conn.execute(query, params)
                connections = [dict(row) for row in cursor.fetchall()]
                
                # Add service names and device names
                for conn_data in connections:
                    conn_data['service_name'] = self._get_service_name(
                        conn_data['dest_ip'], 
                        conn_data['dest_port']
                    )
                    conn_data['device_name'] = self._get_device_name(conn_data['dest_ip'])
                    conn_data['source_device'] = self._get_device_name(conn_data.get('source_ip', ''))
                
                return jsonify({
                    'count': len(connections),
                    'connections': connections,
                    'timeframe_hours': hours
                })
            except Exception as e:
                logger.error(f"Error getting network connections: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/network/map')
        def api_network_map():
            """Get network connection map data (GeoIP visualization)"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                # Aggregate by destination country
                cursor = conn.execute('''
                    SELECT dest_ip, country, city, latitude, longitude,
                           COUNT(*) as connection_count,
                           AVG(threat_score) as avg_threat_score,
                           MAX(threat_score) as max_threat_score,
                           GROUP_CONCAT(DISTINCT process_name) as processes
                    FROM network_events
                    WHERE timestamp > ? AND country != 'Unknown'
                    GROUP BY dest_ip, country
                    ORDER BY max_threat_score DESC, connection_count DESC
                    LIMIT 200
                ''', (cutoff,))
                
                map_data = []
                for row in cursor.fetchall():
                    map_data.append({
                        'ip': row[0],
                        'country': row[1],
                        'city': row[2],
                        'lat': row[3] or 0,
                        'lon': row[4] or 0,
                        'connections': row[5],
                        'avg_threat': round(row[6], 2) if row[6] else 0,
                        'max_threat': row[7] or 0,
                        'processes': row[8].split(',') if row[8] else []
                    })
                
                return jsonify({
                    'locations': map_data,
                    'count': len(map_data),
                    'timeframe_hours': hours
                })
            except Exception as e:
                logger.error(f"Error getting network map: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/network/suspicious')
        def api_network_suspicious():
            """Get high-threat network connections"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                min_score = request.args.get('min_score', default=50, type=int)
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                cursor = conn.execute('''
                    SELECT dest_ip, dest_port, protocol, process_name, process_pid,
                           country, threat_score, timestamp, status
                    FROM network_events
                    WHERE timestamp > ? AND threat_score >= ?
                    ORDER BY threat_score DESC, timestamp DESC
                    LIMIT 100
                ''', (cutoff, min_score))
                
                suspicious = [dict(row) for row in cursor.fetchall()]
                
                return jsonify({
                    'count': len(suspicious),
                    'connections': suspicious,
                    'min_threat_score': min_score
                })
            except Exception as e:
                logger.error(f"Error getting suspicious connections: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/network/stats')
        def api_network_stats():
            """Get network connection statistics"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                stats = {}
                
                # Total connections
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM network_events WHERE timestamp > ?',
                    (cutoff,)
                )
                stats['total_connections'] = cursor.fetchone()[0]
                
                # Suspicious connections
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM network_events WHERE timestamp > ? AND is_suspicious = 1',
                    (cutoff,)
                )
                stats['suspicious_connections'] = cursor.fetchone()[0]
                
                # Unique IPs
                cursor = conn.execute(
                    'SELECT COUNT(DISTINCT dest_ip) FROM network_events WHERE timestamp > ?',
                    (cutoff,)
                )
                stats['unique_ips'] = cursor.fetchone()[0]
                
                # Unique countries
                cursor = conn.execute(
                    'SELECT COUNT(DISTINCT country) FROM network_events WHERE timestamp > ? AND country != "Unknown"',
                    (cutoff,)
                )
                stats['unique_countries'] = cursor.fetchone()[0]
                
                # Top processes by connections
                cursor = conn.execute('''
                    SELECT process_name, COUNT(*) as conn_count
                    FROM network_events
                    WHERE timestamp > ?
                    GROUP BY process_name
                    ORDER BY conn_count DESC
                    LIMIT 10
                ''', (cutoff,))
                stats['top_processes'] = [{'name': row[0], 'connections': row[1]} for row in cursor.fetchall()]
                
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting network stats: {e}")
                return jsonify({'error': str(e)}), 500
        
        # ============= ML API ENDPOINTS =============
        
        @self.app.route('/api/ml/status')
        def api_ml_status():
            """Get ML model status and training readiness"""
            try:
                import os
                from pathlib import Path
                
                conn = self.db._get_connection()
                status = {
                    'is_training': False,
                    'ready_to_train': False,
                    'model_accuracy': None,
                    'false_positive_rate': None,
                    'last_training': None,
                    'training_progress': 0
                }
                
                # Get event counts
                cursor = conn.execute('SELECT COUNT(*) FROM process_events')
                status['process_events'] = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM network_events')
                status['network_events'] = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM file_events')
                status['file_events'] = cursor.fetchone()[0]
                
                # Get labeled data for supervised learning
                cursor = conn.execute('SELECT COUNT(*) FROM alerts WHERE false_positive = 1')
                status['labeled_malicious'] = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM process_events WHERE suspicious_score < 20')
                status['labeled_benign'] = cursor.fetchone()[0]
                
                # Check if ready to train (minimum 1000 events)
                status['ready_to_train'] = status['process_events'] >= 1000
                
                # Check for trained models
                models_dir = Path(self.config['paths'].get('models', 'models/trained'))
                if models_dir.exists():
                    model_files = list(models_dir.glob('*.pkl')) + list(models_dir.glob('*.h5'))
                    if model_files:
                        latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
                        status['last_training'] = int(latest_model.stat().st_mtime)
                        
                        # Check for metrics file
                        metrics_file = models_dir.parent / 'metrics' / 'latest_metrics.json'
                        if metrics_file.exists():
                            with open(metrics_file, 'r') as f:
                                metrics = json.load(f)
                                
                                # Extract metrics from new format
                                status['training_time'] = metrics.get('training_time_seconds', 0.0)
                                status['total_samples_trained'] = metrics.get('total_samples', 0)
                                status['label_distribution'] = metrics.get('label_distribution', {})
                                
                                # Random Forest metrics
                                rf_metrics = metrics.get('models', {}).get('random_forest', {})
                                if rf_metrics:
                                    status['model_accuracy'] = rf_metrics.get('accuracy', 0.0)
                                    status['false_positive_rate'] = rf_metrics.get('false_positive_rate', 0.0)
                                    status['precision'] = rf_metrics.get('precision', 0.0)
                                    status['recall'] = rf_metrics.get('recall', 0.0)
                                    status['f1_score'] = rf_metrics.get('f1_score', 0.0)
                                    status['feature_importance'] = rf_metrics.get('feature_importance', [])
                                
                                # Isolation Forest metrics
                                if_metrics = metrics.get('models', {}).get('isolation_forest', {})
                                if if_metrics:
                                    status['anomalies_detected'] = if_metrics.get('anomalies_detected', 0)
                                    status['anomaly_percentage'] = if_metrics.get('anomaly_percentage', 0.0)
                
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting ML status: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/ml/train', methods=['POST'])
        def api_ml_train():
            """Trigger ML model training"""
            try:
                # Check if data is ready
                conn = self.db._get_connection()
                cursor = conn.execute('SELECT COUNT(*) FROM process_events')
                process_count = cursor.fetchone()[0]
                
                min_samples = self.config.get('ml_models', {}).get('training', {}).get('min_samples', 1000)
                if process_count < min_samples:
                    return jsonify({
                        'status': 'insufficient_data',
                        'message': f'Need at least {min_samples} events, currently have {process_count}'
                    }), 400
                
                # Import and run training pipeline
                from utils.ml_training import MLTrainingPipeline
                
                logger.info(f"Starting ML training with {process_count} events...")
                
                pipeline = MLTrainingPipeline(self.config, self.db)
                result = pipeline.train()
                
                if result['status'] == 'success':
                    metrics = result['metrics']
                    logger.info(f"Training completed in {metrics['training_time_seconds']:.1f}s")
                    
                    return jsonify({
                        'status': 'success',
                        'message': f'Training completed successfully in {metrics["training_time_seconds"]:.1f}s',
                        'metrics': metrics
                    })
                else:
                    return jsonify({
                        'status': 'failed',
                        'message': f'Training failed: {result.get("error", "Unknown error")}',
                        'error': result.get('error')
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error training ML model: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/system/metrics')
        def api_system_metrics():
            """Get real-time system metrics"""
            try:
                import psutil
                
                # CPU usage (1 second sample)
                cpu_percent = psutil.cpu_percent(interval=0.1)
                
                # Memory usage
                memory = psutil.virtual_memory()
                
                # Disk I/O (if available)
                try:
                    disk_io = psutil.disk_io_counters()
                    # Simple heuristic: if read/write bytes are high, show activity
                    disk_io_percent = min(100, (disk_io.read_bytes + disk_io.write_bytes) / (1024**3) * 10)
                except:
                    disk_io_percent = 0
                
                return jsonify({
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_gb': memory.used / (1024**3),
                    'memory_total_gb': memory.total / (1024**3),
                    'disk_io_percent': disk_io_percent,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error getting system metrics: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/health')
        def api_health():
            """System health check with detailed metrics"""
            try:
                import psutil
                import os
                
                health = {
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat()
                }
                
                # Database health and stats
                try:
                    stats = self.db.get_stats()
                    conn = self.db._get_connection()
                    
                    # Get event counts
                    cursor = conn.execute('SELECT COUNT(*) FROM process_events')
                    health['process_events'] = cursor.fetchone()[0]
                    
                    cursor = conn.execute('SELECT COUNT(*) FROM network_events')
                    health['network_events'] = cursor.fetchone()[0]
                    
                    cursor = conn.execute('SELECT COUNT(*) FROM file_events')
                    health['file_events'] = cursor.fetchone()[0]
                    
                    cursor = conn.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0')
                    health['active_alerts'] = cursor.fetchone()[0]
                    
                    # Database size
                    db_path = self.config['paths']['database']
                    if os.path.exists(db_path):
                        health['db_size_bytes'] = os.path.getsize(db_path)
                        health['db_path'] = db_path
                    
                    # Check if collector is active (recent events in last 30 seconds)
                    cutoff = datetime.now().timestamp() - 30
                    cursor = conn.execute(
                        'SELECT MAX(timestamp) as last_event FROM process_events WHERE timestamp > ?',
                        (cutoff,)
                    )
                    row = cursor.fetchone()
                    last_event = row[0] if row and row[0] else None
                    
                    if last_event:
                        health['collector_running'] = True
                        
                        # Calculate uptime from collector process start time
                        try:
                            import psutil
                            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                                if proc.info.get('cmdline') and 'edr_collector_v2.py' in ' '.join(proc.info['cmdline']):
                                    health['uptime_seconds'] = datetime.now().timestamp() - proc.info['create_time']
                                    break
                            else:
                                # Fallback to oldest event if process not found
                                cursor.execute('SELECT MIN(timestamp) FROM process_events')
                                first_event = cursor.fetchone()[0]
                                if first_event:
                                    health['uptime_seconds'] = datetime.now().timestamp() - first_event
                        except Exception as e:
                            logger.error(f"Error calculating uptime: {e}")
                            health['uptime_seconds'] = 0
                    else:
                        health['collector_running'] = False
                        health['status'] = 'degraded'
                    
                except Exception as e:
                    health['status'] = 'degraded'
                    logger.error(f"Database health check failed: {e}")
                
                # NAS availability - check if shares are actually mounted
                nas_shares = ['/Volumes/Apps', '/Volumes/Data', '/Volumes/Docker']
                mounted_shares = [share for share in nas_shares if os.path.exists(share) and os.path.ismount(share)]
                
                health['nas_available'] = len(mounted_shares) >= 2  # At least 2 of 3 shares mounted
                health['nas_shares_mounted'] = mounted_shares
                health['nas_backup_path'] = self.config['paths'].get('nas_backups', '/Volumes/Apps/Services/EDR/backups')
                
                # System resources
                try:
                    health['cpu_percent'] = psutil.cpu_percent(interval=0.1)
                    
                    mem = psutil.virtual_memory()
                    health['memory_mb'] = mem.used / (1024 * 1024)
                    health['memory_percent'] = mem.percent
                    
                    disk = psutil.disk_usage('/')
                    health['disk_percent'] = disk.percent
                    
                    net = psutil.net_io_counters()
                    health['network_bytes_sent'] = net.bytes_sent
                    health['network_bytes_recv'] = net.bytes_recv
                except Exception as e:
                    logger.error(f"System metrics error: {e}")
                
                # Network tracker mode (check for config or existing status)
                health['network_tracker_mode'] = 'psutil (standard)'  # Default
                health['network_tracker_running'] = health.get('collector_running', False)
                health['process_monitor_running'] = health.get('collector_running', False)
                
                # ML model status
                health['ml_model_loaded'] = False
                health['ml_accuracy'] = 0.0
                
                # Calculate uptime if collector running
                if not health.get('uptime_seconds'):
                    health['uptime_seconds'] = 0
                
                # Overall status
                if not health.get('collector_running'):
                    health['status'] = 'degraded'
                elif health.get('active_alerts', 0) > 10:
                    health['status'] = 'warning'
                
                return jsonify(health)
            except Exception as e:
                logger.error(f"Error checking health: {e}")
                return jsonify({
                    'status': 'error',
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/metrics/timeline')
        def api_metrics_timeline():
            """Get timeline metrics for charts"""
            try:
                hours = request.args.get('hours', default=24, type=int)
                
                conn = self.db._get_connection()
                cutoff = datetime.now().timestamp() - (hours * 3600)
                
                # Get event counts per hour
                cursor = conn.execute('''
                    SELECT 
                        CAST(timestamp / 3600 AS INTEGER) * 3600 as hour,
                        COUNT(*) as count
                    FROM process_events
                    WHERE timestamp > ?
                    GROUP BY hour
                    ORDER BY hour
                ''', (cutoff,))
                
                timeline = [{'timestamp': row[0], 'count': row[1]} 
                           for row in cursor.fetchall()]
                
                return jsonify({
                    'timeline': timeline
                })
            except Exception as e:
                logger.error(f"Error getting timeline: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/ups/status')
        def api_ups_status():
            """Get UPS current status and recent events"""
            try:
                conn = self.db._get_connection()
                
                # Get most recent UPS event
                cursor = conn.execute('''
                    SELECT timestamp, event_type, status, battery_charge, runtime_minutes,
                           load_percent, on_battery, low_battery, connected, device_name,
                           alert_triggered
                    FROM ups_events
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''')
                
                row = cursor.fetchone()
                
                if not row:
                    return jsonify({
                        'status': 'unknown',
                        'message': 'No UPS data available'
                    })
                
                status = {
                    'timestamp': row[0],
                    'event_type': row[1],
                    'status': row[2],
                    'battery_charge': row[3],
                    'runtime_minutes': row[4],
                    'load_percent': row[5],
                    'on_battery': bool(row[6]),
                    'low_battery': bool(row[7]),
                    'connected': bool(row[8]),
                    'device_name': row[9],
                    'alert_triggered': bool(row[10]),
                    'last_update': datetime.fromtimestamp(row[0]).isoformat()
                }
                
                # Get recent disconnect events (last 24h)
                cutoff = datetime.now().timestamp() - (24 * 3600)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM ups_events
                    WHERE timestamp > ? AND event_type = 'ups_disconnected'
                ''', (cutoff,))
                
                status['disconnects_24h'] = cursor.fetchone()[0]
                
                return jsonify(status)
                
            except Exception as e:
                logger.error(f"Error getting UPS status: {e}")
                return jsonify({'error': str(e)}), 500
        
        # ============= HELPER METHODS =============
    
    def _register_socketio_events(self):
        """Register WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Client connected to WebSocket"""
            logger.info(f"Client connected to WebSocket")
            emit('connection_response', {'status': 'connected', 'message': 'Real-time updates enabled'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client disconnected from WebSocket"""
            logger.info(f"Client disconnected from WebSocket")
        
        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            """Client subscribes to specific event types"""
            event_type = data.get('type', 'all')
            logger.info(f"Client subscribed to: {event_type}")
            emit('subscribe_response', {'status': 'subscribed', 'type': event_type})
    
    def broadcast_threat_alert(self, threat_data: Dict):
        """Broadcast new threat alert to all connected clients"""
        try:
            self.socketio.emit('threat_alert', threat_data, namespace='/')
            logger.debug(f"Broadcasted threat alert: {threat_data.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Error broadcasting threat alert: {e}")
    
    def broadcast_stats_update(self, stats: Dict):
        """Broadcast stats update to all connected clients"""
        try:
            self.socketio.emit('stats_update', stats, namespace='/')
        except Exception as e:
            logger.error(f"Error broadcasting stats: {e}")
    
    def start_background_updates(self):
        """Start background thread for periodic updates"""
        import threading
        import time
        
        def background_thread():
            """Background worker that pushes updates every 5 seconds"""
            last_event_id = 0
            
            while True:
                try:
                    time.sleep(5)  # Update every 5 seconds
                    
                    # Get latest stats
                    stats = self.db.get_stats()
                    self.broadcast_stats_update({
                        'total_processes': stats.get('total_processes', 0),
                        'suspicious_processes': stats.get('suspicious_processes', 0),
                        'active_alerts': stats.get('active_alerts', 0),
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Check for new high-severity alerts
                    conn = self.db._get_connection()
                    cursor = conn.execute(
                        'SELECT id, severity, threat_type, timestamp FROM alerts WHERE id > ? AND severity IN ("high", "critical") ORDER BY id LIMIT 10',
                        (last_event_id,)
                    )
                    
                    for row in cursor.fetchall():
                        alert_data = {
                            'id': row[0],
                            'severity': row[1],
                            'description': row[2],  # threat_type used as description
                            'timestamp': row[3]
                        }
                        self.broadcast_threat_alert(alert_data)
                        last_event_id = max(last_event_id, row[0])
                    
                except Exception as e:
                    logger.error(f"Background update error: {e}")
        
        # Start background thread
        thread = threading.Thread(target=background_thread, daemon=True)
        thread.start()
        logger.info("Background WebSocket updates started")
    
    def _get_uptime(self) -> Dict[str, Any]:
        """Get system uptime"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
        except:
            # macOS doesn't have /proc/uptime
            import subprocess
            result = subprocess.run(['sysctl', '-n', 'kern.boottime'],
                                  capture_output=True, text=True)
            # Parse boot time and calculate uptime
            uptime_seconds = 0  # Simplified for now
        
        return {
            'seconds': uptime_seconds,
            'formatted': str(timedelta(seconds=int(uptime_seconds)))
        }
    
    def _check_nas_connection(self) -> str:
        """Check if NAS is connected"""
        if not self.config['nas']['enabled']:
            return 'disabled'
        
        nas_ip = self.config['nas']['ip']
        
        try:
            import subprocess
            result = subprocess.run(['ping', '-c', '1', '-W', '1', nas_ip],
                                  capture_output=True, timeout=2)
            return 'connected' if result.returncode == 0 else 'disconnected'
        except:
            return 'unknown'
    
    def _get_disk_space(self) -> Dict[str, Any]:
        """Get disk space information"""
        try:
            import shutil
            db_path = Path(self.config['paths']['database'])
            usage = shutil.disk_usage(db_path.parent)
            
            return {
                'total_gb': usage.total / (1024**3),
                'used_gb': usage.used / (1024**3),
                'free_gb': usage.free / (1024**3),
                'percent_used': (usage.used / usage.total) * 100
            }
        except:
            return {'error': 'unavailable'}
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            
            return {
                'total_gb': mem.total / (1024**3),
                'used_gb': mem.used / (1024**3),
                'percent_used': mem.percent
            }
        except:
            return {'error': 'unavailable'}
    
    def run(self, host='127.0.0.1', port=5050, debug=False, ssl_context=None):
        """Run the dashboard server with WebSocket support"""
        protocol = "https" if ssl_context else "http"
        logger.info(f"Starting EDR Dashboard on {protocol}://{host}:{port}")
        logger.info("WebSocket real-time updates enabled")
        if ssl_context:
            logger.info("SSL/HTTPS enabled")
        logger.info("Press Ctrl+C to stop")
        
        # Start background update thread
        self.start_background_updates()
        
        try:
            # Use socketio.run instead of app.run for WebSocket support
            if ssl_context:
                self.socketio.run(self.app, host=host, port=port, debug=debug, 
                                allow_unsafe_werkzeug=True, ssl_context=ssl_context)
            else:
                self.socketio.run(self.app, host=host, port=port, debug=debug, 
                                allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            logger.info("Shutting down dashboard...")
        finally:
            if self.db:
                self.db.close()


def main():
    """Main entry point"""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    
    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        dashboard = DashboardApp(str(config_path))
        
        # Check for SSL certificate
        ssl_dir = Path(__file__).parent.parent / 'ssl'
        cert_file = ssl_dir / 'cert.pem'
        key_file = ssl_dir / 'key.pem'
        
        ssl_context = None
        if cert_file.exists() and key_file.exists():
            # Create production-grade SSL context
            import ssl
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(str(cert_file), str(key_file))
            
            # Modern TLS configuration
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
            
            # Strong cipher suites (prioritize TLS 1.3, then strong TLS 1.2)
            ssl_context.set_ciphers(
                'TLS_AES_256_GCM_SHA384:'
                'TLS_CHACHA20_POLY1305_SHA256:'
                'TLS_AES_128_GCM_SHA256:'
                'ECDHE+AESGCM:'
                'ECDHE+CHACHA20:'
                '!aNULL:!MD5:!DSS'
            )
            
            # Additional security options
            ssl_context.options |= ssl.OP_NO_COMPRESSION  # Prevent CRIME attack
            ssl_context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE  # Server chooses cipher
            ssl_context.options |= ssl.OP_SINGLE_DH_USE  # Generate new DH key for each connection
            ssl_context.options |= ssl.OP_SINGLE_ECDH_USE  # Generate new ECDH key for each connection
            
            logger.info("Using production-grade SSL/TLS configuration")
            logger.info(f"  TLS versions: 1.2 - 1.3")
            logger.info(f"  Certificate: {cert_file}")
        else:
            logger.warning("No SSL certificate found - dashboard will use HTTP")
            logger.warning("Run: cd ssl && ./generate_production_certs.sh")
        
        dashboard.run(host='0.0.0.0', port=5050, debug=False, ssl_context=ssl_context)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
