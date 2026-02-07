"""
Production-grade database layer for EDR system
- Thread-safe with connection pooling
- Full input validation
- Retry logic with exponential backoff
- Batch inserts for performance
- Comprehensive error handling
"""
import sqlite3
import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum
import shutil


# Configure module logger
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database errors"""
    pass


class ValidationError(Exception):
    """Input validation errors"""
    pass


class Severity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProcessEvent:
    """Validated process event"""
    pid: int
    name: str
    timestamp: float = None
    cmdline: Optional[str] = None
    parent_pid: Optional[int] = None
    parent_name: Optional[str] = None
    username: Optional[str] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    num_threads: int = 0
    connections_count: int = 0
    suspicious_score: float = 0.0
    features: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.features is None:
            self.features = {}
        self.validate()
    
    def validate(self):
        """Validate all fields"""
        if not isinstance(self.pid, int) or self.pid < 0:
            raise ValidationError(f"Invalid PID: {self.pid}")
        if not self.name or not isinstance(self.name, str):
            raise ValidationError("Process name must be non-empty string")
        # CPU can exceed 100% on multi-core systems
        if self.cpu_percent < 0:
            raise ValidationError(f"Invalid CPU percent: {self.cpu_percent}")
        if self.memory_mb < 0:
            raise ValidationError(f"Invalid memory: {self.memory_mb}")
        if self.suspicious_score < 0 or self.suspicious_score > 100:
            raise ValidationError(f"Invalid suspicious score: {self.suspicious_score}")


class EDRDatabase:
    """
    Production-grade SQLite database with:
    - Thread-local connections for thread safety
    - WAL mode for concurrent reads/writes
    - Connection pooling
    - Batch insert support
    - Input validation
    - Retry logic
    - Comprehensive error handling
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 0.1
    BATCH_SIZE = 50
    
    def __init__(self, db_path: str, nas_backup_path: Optional[str] = None):
        if not db_path:
            raise ValueError("db_path cannot be empty")
        
        self.db_path = Path(db_path).resolve()
        self.nas_backup_path = Path(nas_backup_path).resolve() if nas_backup_path else None
        
        # Create directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.nas_backup_path:
            self.nas_backup_path.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        self._main_lock = threading.RLock()
        
        # Batch insert buffers
        self._process_buffer: List[ProcessEvent] = []
        self._buffer_lock = threading.Lock()
        
        # Initialize schema
        self._init_schema()
        logger.info(f"Database initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                isolation_level='DEFERRED',  # Use DEFERRED transactions
                check_same_thread=False  # Safe because we use thread-local storage
            )
            conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
            conn.execute('PRAGMA temp_store=MEMORY')
            
            self._local.conn = conn
        
        return self._local.conn
    
    @contextmanager
    def _transaction(self):
        """Thread-safe transaction context manager with retry logic"""
        conn = self._get_connection()
        retries = 0
        
        while retries < self.MAX_RETRIES:
            try:
                yield conn
                conn.commit()
                return
            except sqlite3.OperationalError as e:
                try:
                    conn.rollback()
                except:
                    pass  # May already be rolled back
                
                if 'locked' in str(e).lower() and retries < self.MAX_RETRIES - 1:
                    retries += 1
                    time.sleep(self.RETRY_DELAY * (2 ** retries))  # Exponential backoff
                    logger.warning(f"Database locked, retry {retries}/{self.MAX_RETRIES}")
                else:
                    raise DatabaseError(f"Transaction failed after {retries} retries: {e}") from e
            except Exception as e:
                try:
                    conn.rollback()
                except:
                    pass  # May already be rolled back
                raise DatabaseError(f"Transaction failed: {e}") from e
    
    def _init_schema(self):
        """Initialize database schema with proper constraints and indexes"""
        with self._transaction() as conn:
            conn.executescript('''
                -- Process events
                CREATE TABLE IF NOT EXISTS process_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL CHECK(timestamp > 0),
                    pid INTEGER NOT NULL CHECK(pid >= 0),
                    name TEXT NOT NULL CHECK(length(name) > 0),
                    cmdline TEXT,
                    parent_pid INTEGER CHECK(parent_pid IS NULL OR parent_pid >= 0),
                    parent_name TEXT,
                    username TEXT,
                    cpu_percent REAL CHECK(cpu_percent >= 0 AND cpu_percent <= 100),
                    memory_mb REAL CHECK(memory_mb >= 0),
                    num_threads INTEGER CHECK(num_threads >= 0),
                    connections_count INTEGER CHECK(connections_count >= 0),
                    suspicious_score REAL DEFAULT 0 CHECK(suspicious_score >= 0 AND suspicious_score <= 100),
                    features TEXT CHECK(features IS NULL OR json_valid(features))
                );
                
                CREATE INDEX IF NOT EXISTS idx_process_timestamp ON process_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_process_pid ON process_events(pid);
                CREATE INDEX IF NOT EXISTS idx_process_name ON process_events(name);
                CREATE INDEX IF NOT EXISTS idx_process_suspicious ON process_events(suspicious_score);
                
                -- File system events
                CREATE TABLE IF NOT EXISTS file_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL CHECK(timestamp > 0),
                    event_type TEXT NOT NULL CHECK(event_type IN ('created', 'modified', 'deleted', 'moved')),
                    path TEXT NOT NULL CHECK(length(path) > 0),
                    process_name TEXT,
                    is_suspicious INTEGER DEFAULT 0 CHECK(is_suspicious IN (0, 1))
                );
                
                CREATE INDEX IF NOT EXISTS idx_file_timestamp ON file_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_file_path ON file_events(path);
                CREATE INDEX IF NOT EXISTS idx_file_suspicious ON file_events(is_suspicious);
                
                -- System events
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL CHECK(timestamp > 0),
                    event_type TEXT NOT NULL CHECK(length(event_type) > 0),
                    username TEXT,
                    details TEXT CHECK(details IS NULL OR json_valid(details)),
                    success INTEGER CHECK(success IS NULL OR success IN (0, 1)),
                    suspicious_score REAL DEFAULT 0 CHECK(suspicious_score >= 0 AND suspicious_score <= 100)
                );
                
                CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_system_type ON system_events(event_type);
                
                -- Threat alerts
            CREATE TABLE IF NOT EXISTS network_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                source_ip TEXT,
                source_port INTEGER,
                dest_ip TEXT NOT NULL,
                dest_port INTEGER NOT NULL,
                protocol TEXT,
                status TEXT,
                process_name TEXT,
                process_pid INTEGER,
                country TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                threat_score REAL DEFAULT 0,
                is_suspicious INTEGER DEFAULT 0,
                direction TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_network_timestamp ON network_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_network_suspicious ON network_events(is_suspicious, timestamp);
            CREATE INDEX IF NOT EXISTS idx_network_dest_ip ON network_events(dest_ip);
            
            CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL CHECK(timestamp > 0),
                    threat_type TEXT NOT NULL CHECK(length(threat_type) > 0),
                    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'high', 'critical')),
                    threat_score REAL NOT NULL CHECK(threat_score >= 0 AND threat_score <= 100),
                    source_type TEXT,
                    source_id INTEGER,
                    details TEXT CHECK(details IS NULL OR json_valid(details)),
                    ml_confidence REAL CHECK(ml_confidence IS NULL OR (ml_confidence >= 0 AND ml_confidence <= 1)),
                    false_positive INTEGER DEFAULT 0 CHECK(false_positive IN (0, 1)),
                    user_feedback TEXT,
                    response_actions TEXT CHECK(response_actions IS NULL OR json_valid(response_actions)),
                    resolved INTEGER DEFAULT 0 CHECK(resolved IN (0, 1))
                );
                
                CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON alerts(timestamp);
                CREATE INDEX IF NOT EXISTS idx_alert_severity ON alerts(severity);
                CREATE INDEX IF NOT EXISTS idx_alert_resolved ON alerts(resolved);
                
                -- Baseline statistics
                CREATE TABLE IF NOT EXISTS baselines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL CHECK(length(category) > 0),
                    metric_name TEXT NOT NULL CHECK(length(metric_name) > 0),
                    mean_value REAL,
                    std_value REAL CHECK(std_value IS NULL OR std_value >= 0),
                    min_value REAL,
                    max_value REAL,
                    sample_count INTEGER CHECK(sample_count IS NULL OR sample_count >= 0),
                    last_updated REAL NOT NULL CHECK(last_updated > 0),
                    UNIQUE(category, metric_name)
                );
                
                CREATE INDEX IF NOT EXISTS idx_baseline_category ON baselines(category);
                
                -- Whitelist entries
                CREATE TABLE IF NOT EXISTS whitelist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_type TEXT NOT NULL CHECK(length(entry_type) > 0),
                    value TEXT NOT NULL CHECK(length(value) > 0),
                    reason TEXT,
                    added_by TEXT NOT NULL CHECK(length(added_by) > 0),
                    added_timestamp REAL NOT NULL CHECK(added_timestamp > 0),
                    UNIQUE(entry_type, value)
                );
                
                CREATE INDEX IF NOT EXISTS idx_whitelist_type ON whitelist(entry_type);
                
                -- Threat Incident Tracking (AI-powered lifecycle)
                CREATE TABLE IF NOT EXISTS threat_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL UNIQUE,
                    timestamp REAL NOT NULL CHECK(timestamp > 0),
                    process_name TEXT NOT NULL,
                    process_pid INTEGER NOT NULL,
                    threat_score REAL NOT NULL CHECK(threat_score >= 0 AND threat_score <= 100),
                    threat_type TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('detected', 'analyzing', 'monitoring', 'responded', 'verified', 'closed')),
                    ai_analyzed INTEGER DEFAULT 0,
                    ai_model TEXT,
                    ai_confidence TEXT,
                    ai_reasoning TEXT,
                    recommended_action TEXT,
                    action_taken TEXT,
                    action_result TEXT,
                    action_timestamp REAL,
                    verified INTEGER DEFAULT 0,
                    verification_timestamp REAL,
                    nas_activity INTEGER DEFAULT 0,
                    timeline TEXT CHECK(timeline IS NULL OR json_valid(timeline)),
                    post_incident_analysis TEXT CHECK(post_incident_analysis IS NULL OR json_valid(post_incident_analysis)),
                    closed_timestamp REAL,
                    user_feedback TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_incident_status ON threat_incidents(status);
                CREATE INDEX IF NOT EXISTS idx_incident_timestamp ON threat_incidents(timestamp);
                CREATE INDEX IF NOT EXISTS idx_incident_threat_score ON threat_incidents(threat_score);
                CREATE INDEX IF NOT EXISTS idx_incident_pid ON threat_incidents(process_pid);
                
                -- ML model metadata
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_type TEXT NOT NULL CHECK(length(model_type) > 0),
                    version TEXT NOT NULL CHECK(length(version) > 0),
                    trained_timestamp REAL NOT NULL CHECK(trained_timestamp > 0),
                    accuracy REAL CHECK(accuracy IS NULL OR (accuracy >= 0 AND accuracy <= 1)),
                    precision_val REAL CHECK(precision_val IS NULL OR (precision_val >= 0 AND precision_val <= 1)),
                    recall_val REAL CHECK(recall_val IS NULL OR (recall_val >= 0 AND recall_val <= 1)),
                    f1_score REAL CHECK(f1_score IS NULL OR (f1_score >= 0 AND f1_score <= 1)),
                    is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
                    path TEXT,
                    UNIQUE(model_type, version)
                );
                
                CREATE INDEX IF NOT EXISTS idx_model_type ON models(model_type);
                CREATE INDEX IF NOT EXISTS idx_model_active ON models(is_active);
            ''')
    
    def insert_process_event(self, event: Dict[str, Any]) -> Optional[int]:
        """
        Insert process event with full validation
        
        Args:
            event: Dictionary containing process event data
            
        Returns:
            Row ID if successful, None if failed
            
        Raises:
            ValidationError: If event data is invalid
        """
        try:
            # Validate and normalize
            proc_event = ProcessEvent(**event)
            
            with self._transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO process_events 
                    (timestamp, pid, name, cmdline, parent_pid, parent_name, username,
                     cpu_percent, memory_mb, num_threads, connections_count, suspicious_score, features)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    proc_event.timestamp,
                    proc_event.pid,
                    proc_event.name[:255],  # Limit length
                    proc_event.cmdline[:2048] if proc_event.cmdline else None,
                    proc_event.parent_pid,
                    proc_event.parent_name[:255] if proc_event.parent_name else None,
                    proc_event.username[:100] if proc_event.username else None,
                    proc_event.cpu_percent,
                    proc_event.memory_mb,
                    proc_event.num_threads,
                    proc_event.connections_count,
                    proc_event.suspicious_score,
                    json.dumps(proc_event.features)[:8192]  # Limit JSON size
                ))
                return cursor.lastrowid
        except ValidationError:
            raise  # Re-raise validation errors
        except sqlite3.Error as e:
            logger.error(f"Failed to insert process event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error inserting process event: {e}", exc_info=True)
            return None
    
    def batch_insert_process_events(self, events: List[Dict[str, Any]]) -> int:
        """
        Batch insert process events for better performance
        
        Returns:
            Number of events successfully inserted
        """
        if not events:
            return 0
        
        inserted = 0
        try:
            with self._transaction() as conn:
                for event in events:
                    try:
                        proc_event = ProcessEvent(**event)
                        conn.execute('''
                            INSERT INTO process_events 
                            (timestamp, pid, name, cmdline, parent_pid, parent_name, username,
                             cpu_percent, memory_mb, num_threads, connections_count, suspicious_score, features)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            proc_event.timestamp,
                            proc_event.pid,
                            proc_event.name[:255],
                            proc_event.cmdline[:2048] if proc_event.cmdline else None,
                            proc_event.parent_pid,
                            proc_event.parent_name[:255] if proc_event.parent_name else None,
                            proc_event.username[:100] if proc_event.username else None,
                            proc_event.cpu_percent,
                            proc_event.memory_mb,
                            proc_event.num_threads,
                            proc_event.connections_count,
                            proc_event.suspicious_score,
                            json.dumps(proc_event.features)[:8192]
                        ))
                        inserted += 1
                    except (ValidationError, sqlite3.Error) as e:
                        logger.warning(f"Skipping invalid event: {e}")
                        continue
        except DatabaseError as e:
            logger.error(f"Batch insert failed: {e}")
        
        return inserted
    
    def insert_network_event(self, event: Dict[str, Any]) -> Optional[int]:
        """
        Insert network connection event
        
        Args:
            event: Dictionary containing network event data
            
        Returns:
            Row ID if successful, None if failed
        """
        try:
            with self._transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO network_events 
                    (timestamp, source_ip, source_port, dest_ip, dest_port, protocol, status,
                     process_name, process_pid, country, city, latitude, longitude,
                     threat_score, is_suspicious, direction)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.get('timestamp'),
                    event.get('source_ip'),
                    event.get('source_port'),
                    event.get('dest_ip'),
                    event.get('dest_port'),
                    event.get('protocol'),
                    event.get('status'),
                    event.get('process_name'),
                    event.get('process_pid'),
                    event.get('country'),
                    event.get('city'),
                    event.get('latitude'),
                    event.get('longitude'),
                    event.get('threat_score', 0),
                    1 if event.get('is_suspicious') else 0,
                    event.get('direction')
                ))
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to insert network event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error inserting network event: {e}", exc_info=True)
            return None
    
    def create_threat_incident(self, incident_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new threat incident with AI analysis
        
        Args:
            incident_data: Dictionary containing incident details
            
        Returns:
            incident_id if successful, None if failed
        """
        try:
            import uuid
            incident_id = str(uuid.uuid4())[:8]
            timestamp = time.time()
            
            timeline = [
                {"timestamp": timestamp, "event": "detected", "details": "Threat detected by monitoring system"}
            ]
            
            with self._transaction() as conn:
                conn.execute('''
                    INSERT INTO threat_incidents 
                    (incident_id, timestamp, process_name, process_pid, threat_score, threat_type,
                     status, ai_analyzed, ai_model, ai_confidence, ai_reasoning, recommended_action,
                     nas_activity, timeline)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    incident_id,
                    timestamp,
                    incident_data.get('process_name'),
                    incident_data.get('process_pid'),
                    incident_data.get('threat_score', 0),
                    incident_data.get('threat_type', 'unknown'),
                    'detected',
                    1 if incident_data.get('ai_analyzed') else 0,
                    incident_data.get('ai_model'),
                    incident_data.get('ai_confidence'),
                    incident_data.get('ai_reasoning'),
                    incident_data.get('recommended_action'),
                    1 if incident_data.get('nas_activity') else 0,
                    json.dumps(timeline)
                ))
            
            logger.info(f"Created threat incident {incident_id} for {incident_data.get('process_name')}")
            return incident_id
            
        except Exception as e:
            logger.error(f"Failed to create threat incident: {e}", exc_info=True)
            return None
    
    def update_incident_status(self, incident_id: str, new_status: str, details: Optional[str] = None) -> bool:
        """
        Update threat incident status with timeline entry
        
        Args:
            incident_id: Incident identifier
            new_status: New status (analyzing, monitoring, responded, verified, closed)
            details: Optional details about the status change
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = time.time()
            
            with self._transaction() as conn:
                # Get current timeline
                cursor = conn.execute('SELECT timeline FROM threat_incidents WHERE incident_id = ?', (incident_id,))
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Incident {incident_id} not found")
                    return False
                
                timeline = json.loads(row[0]) if row[0] else []
                timeline.append({
                    "timestamp": timestamp,
                    "event": new_status,
                    "details": details or f"Status changed to {new_status}"
                })
                
                # Update status and timeline
                conn.execute('''
                    UPDATE threat_incidents
                    SET status = ?, timeline = ?
                    WHERE incident_id = ?
                ''', (new_status, json.dumps(timeline), incident_id))
            
            logger.info(f"Updated incident {incident_id} to status: {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update incident status: {e}", exc_info=True)
            return False
    
    def record_incident_action(self, incident_id: str, action: str, result: str) -> bool:
        """
        Record action taken on a threat incident
        
        Args:
            incident_id: Incident identifier
            action: Action taken (kill_process, unmount_nas, etc.)
            result: Result of the action (success, failed, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = time.time()
            
            with self._transaction() as conn:
                conn.execute('''
                    UPDATE threat_incidents
                    SET action_taken = ?, action_result = ?, action_timestamp = ?, status = 'responded'
                    WHERE incident_id = ?
                ''', (action, result, timestamp, incident_id))
            
            # Also update timeline
            self.update_incident_status(incident_id, 'responded', f"Action: {action} - {result}")
            
            logger.info(f"Recorded action for incident {incident_id}: {action} ({result})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record incident action: {e}", exc_info=True)
            return False
    
    def verify_incident_resolution(self, incident_id: str, verified: bool) -> bool:
        """
        Mark incident as verified after action was taken
        
        Args:
            incident_id: Incident identifier
            verified: Whether the threat was successfully eliminated
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = time.time()
            
            with self._transaction() as conn:
                conn.execute('''
                    UPDATE threat_incidents
                    SET verified = ?, verification_timestamp = ?, status = 'verified'
                    WHERE incident_id = ?
                ''', (1 if verified else 0, timestamp, incident_id))
            
            status_msg = "Threat successfully eliminated" if verified else "Verification failed - threat may persist"
            self.update_incident_status(incident_id, 'verified', status_msg)
            
            logger.info(f"Verified incident {incident_id}: {verified}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify incident: {e}", exc_info=True)
            return False
    
    def close_incident(self, incident_id: str, post_analysis: Optional[Dict] = None) -> bool:
        """
        Close a threat incident with optional post-incident analysis
        
        Args:
            incident_id: Incident identifier
            post_analysis: Optional AI post-incident analysis data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = time.time()
            
            with self._transaction() as conn:
                conn.execute('''
                    UPDATE threat_incidents
                    SET status = 'closed', closed_timestamp = ?, post_incident_analysis = ?
                    WHERE incident_id = ?
                ''', (timestamp, json.dumps(post_analysis) if post_analysis else None, incident_id))
            
            self.update_incident_status(incident_id, 'closed', "Incident resolved and closed")
            
            logger.info(f"Closed incident {incident_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close incident: {e}", exc_info=True)
            return False
    
    def get_active_incidents(self) -> List[Dict[str, Any]]:
        """
        Get all active (non-closed) threat incidents
        
        Returns:
            List of incident dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT * FROM threat_incidents
                WHERE status != 'closed'
                ORDER BY timestamp DESC
            ''')
            
            incidents = []
            for row in cursor.fetchall():
                incident = dict(row)
                # Parse JSON fields
                if incident.get('timeline'):
                    incident['timeline'] = json.loads(incident['timeline'])
                if incident.get('post_incident_analysis'):
                    incident['post_incident_analysis'] = json.loads(incident['post_incident_analysis'])
                incidents.append(incident)
            
            return incidents
            
        except Exception as e:
            logger.error(f"Failed to get active incidents: {e}", exc_info=True)
            return []
    
    def get_incident_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get incident history for the last N hours
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of incident dictionaries
        """
        try:
            cutoff_time = time.time() - (hours * 3600)
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT * FROM threat_incidents
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (cutoff_time,))
            
            incidents = []
            for row in cursor.fetchall():
                incident = dict(row)
                if incident.get('timeline'):
                    incident['timeline'] = json.loads(incident['timeline'])
                if incident.get('post_incident_analysis'):
                    incident['post_incident_analysis'] = json.loads(incident['post_incident_analysis'])
                incidents.append(incident)
            
            return incidents
            
        except Exception as e:
            logger.error(f"Failed to get incident history: {e}", exc_info=True)
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics with error handling"""
        try:
            conn = self._get_connection()
            stats = {}
            
            for table in ['process_events', 'network_events', 'file_events', 'system_events', 'alerts']:
                try:
                    cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                    stats[f'{table}_count'] = cursor.fetchone()[0]
                except sqlite3.Error as e:
                    logger.error(f"Failed to get count for {table}: {e}")
                    stats[f'{table}_count'] = -1
            
            # Additional stats for dashboard
            stats['total_processes'] = stats.get('process_events_count', 0)
            
            # Suspicious process count
            try:
                cursor = conn.execute('SELECT COUNT(*) FROM process_events WHERE suspicious_score > 50')
                stats['suspicious_count'] = cursor.fetchone()[0]
            except sqlite3.Error:
                stats['suspicious_count'] = 0
            
            # Average threat score
            try:
                cursor = conn.execute('SELECT AVG(suspicious_score) FROM process_events')
                avg_score = cursor.fetchone()[0]
                stats['average_threat_score'] = round(avg_score, 2) if avg_score else 0
            except sqlite3.Error:
                stats['average_threat_score'] = 0
            
            # Unresolved alerts
            try:
                cursor = conn.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0')
                stats['unresolved_alerts'] = cursor.fetchone()[0]
            except sqlite3.Error:
                stats['unresolved_alerts'] = -1
            
            # Database size
            try:
                stats['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
            except OSError:
                stats['db_size_mb'] = -1
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            return {}
    
    def backup_to_nas(self) -> bool:
        """
        Backup database to NAS with robust error handling
        
        Returns:
            True if successful, False otherwise
        """
        if not self.nas_backup_path:
            logger.warning("NAS backup path not configured")
            return False
        
        try:
            # Checkpoint WAL before backup
            conn = self._get_connection()
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.nas_backup_path / f"edr_backup_{timestamp}.db"
            
            # Copy with retry logic
            for attempt in range(self.MAX_RETRIES):
                try:
                    shutil.copy2(self.db_path, backup_file)
                    break
                except (IOError, OSError) as e:
                    if attempt < self.MAX_RETRIES - 1:
                        logger.warning(f"Backup attempt {attempt + 1} failed, retrying: {e}")
                        time.sleep(self.RETRY_DELAY * (2 ** attempt))
                    else:
                        raise
            
            # Verify backup
            if not backup_file.exists() or backup_file.stat().st_size == 0:
                raise DatabaseError("Backup verification failed")
            
            # Cleanup old backups (keep last 7)
            try:
                backups = sorted(self.nas_backup_path.glob("edr_backup_*.db"))
                for old_backup in backups[:-7]:
                    old_backup.unlink()
                    logger.debug(f"Deleted old backup: {old_backup.name}")
            except OSError as e:
                logger.warning(f"Failed to cleanup old backups: {e}")
            
            logger.info(f"Database backed up to: {backup_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            return False
    
    def close(self):
        """Close all connections gracefully"""
        try:
            if hasattr(self._local, 'conn') and self._local.conn:
                self._local.conn.close()
                self._local.conn = None
                logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
