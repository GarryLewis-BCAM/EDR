"""Database layer for EDR system - SQLite with NAS backup support"""
import sqlite3
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from contextlib import contextmanager
import shutil


class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass


class EDRDatabase:
    """Thread-safe SQLite database with connection pooling"""
    
    def __init__(self, db_path: str, nas_backup_path: Optional[str] = None):
        if not db_path:
            raise ValueError("db_path cannot be empty")
            
        self.db_path = Path(db_path)
        self.nas_backup_path = Path(nas_backup_path) if nas_backup_path else None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        self._lock = threading.RLock()
        self._insert_buffer = []
        self._buffer_lock = threading.Lock()
        self._max_buffer_size = 100
        
        # Initialize schema
        self._initialize_schema()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                isolation_level='DEFERRED'
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute('PRAGMA journal_mode=WAL')
            self._local.conn.execute('PRAGMA synchronous=NORMAL')
        return self._local.conn
        
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Transaction failed: {e}") from e
        
    def _initialize_schema(self):
        """Initialize database schema with proper constraints"""
        conn = self._get_connection()
        
        # Create tables with proper constraints
        conn.executescript('''
            -- Process events
            CREATE TABLE IF NOT EXISTS process_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cmdline TEXT,
                parent_pid INTEGER,
                parent_name TEXT,
                username TEXT,
                cpu_percent REAL,
                memory_mb REAL,
                num_threads INTEGER,
                connections_count INTEGER,
                suspicious_score REAL DEFAULT 0,
                features TEXT,
                INDEX idx_timestamp (timestamp),
                INDEX idx_pid (pid),
                INDEX idx_name (name)
            );
            
            -- Network connections
            CREATE TABLE IF NOT EXISTS network_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                pid INTEGER,
                process_name TEXT,
                local_addr TEXT,
                local_port INTEGER,
                remote_addr TEXT,
                remote_port INTEGER,
                status TEXT,
                protocol TEXT,
                suspicious_score REAL DEFAULT 0,
                INDEX idx_timestamp (timestamp),
                INDEX idx_remote_addr (remote_addr)
            );
            
            -- File system events
            CREATE TABLE IF NOT EXISTS file_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                path TEXT NOT NULL,
                process_name TEXT,
                is_suspicious BOOLEAN DEFAULT 0,
                INDEX idx_timestamp (timestamp),
                INDEX idx_path (path)
            );
            
            -- System events
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                username TEXT,
                details TEXT,
                success BOOLEAN,
                suspicious_score REAL DEFAULT 0,
                INDEX idx_timestamp (timestamp),
                INDEX idx_event_type (event_type)
            );
            
            -- Threat alerts
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                threat_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                threat_score REAL NOT NULL,
                source_type TEXT,
                source_id INTEGER,
                details TEXT,
                ml_confidence REAL,
                false_positive BOOLEAN DEFAULT 0,
                user_feedback TEXT,
                response_actions TEXT,
                resolved BOOLEAN DEFAULT 0,
                INDEX idx_timestamp (timestamp),
                INDEX idx_severity (severity),
                INDEX idx_resolved (resolved)
            );
            
            -- Baseline statistics
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                mean_value REAL,
                std_value REAL,
                min_value REAL,
                max_value REAL,
                sample_count INTEGER,
                last_updated REAL,
                UNIQUE(category, metric_name)
            );
            
            -- Whitelist entries
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                value TEXT NOT NULL,
                reason TEXT,
                added_by TEXT,
                added_timestamp REAL NOT NULL,
                UNIQUE(entry_type, value)
            );
            
            -- ML model metadata
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_type TEXT NOT NULL,
                version TEXT NOT NULL,
                trained_timestamp REAL NOT NULL,
                accuracy REAL,
                precision_val REAL,
                recall_val REAL,
                f1_score REAL,
                is_active BOOLEAN DEFAULT 1,
                path TEXT,
                INDEX idx_model_type (model_type),
                INDEX idx_is_active (is_active)
            );
        ''')
        conn.commit()
        
    def insert_process_event(self, event: Dict[str, Any]) -> Optional[int]:
        """Insert process event with validation"""
        # Validate required fields
        if 'pid' not in event or 'name' not in event:
            raise ValueError("Process event must have 'pid' and 'name' fields")
        
        if not isinstance(event['pid'], int) or event['pid'] < 0:
            raise ValueError(f"Invalid PID: {event.get('pid')}")
        
        try:
            with self._transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO process_events 
                    (timestamp, pid, name, cmdline, parent_pid, parent_name, username,
                     cpu_percent, memory_mb, num_threads, connections_count, suspicious_score, features)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.get('timestamp', time.time()),
                    event['pid'],
                    str(event['name'])[:255],  # Limit length
                    str(event.get('cmdline', ''))[:2048] if event.get('cmdline') else None,
                    event.get('parent_pid'),
                    str(event.get('parent_name', ''))[:255] if event.get('parent_name') else None,
                    str(event.get('username', ''))[:100] if event.get('username') else None,
                    float(event.get('cpu_percent', 0.0)),
                    float(event.get('memory_mb', 0.0)),
                    int(event.get('num_threads', 0)),
                    int(event.get('connections_count', 0)),
                    float(event.get('suspicious_score', 0.0)),
                    json.dumps(event.get('features', {}))[:4096]  # Limit JSON size
                ))
                return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Failed to insert process event: {e}")
            return None
        
    def insert_network_event(self, event: Dict[str, Any]) -> int:
        """Insert network connection event"""
        cursor = self.conn.execute('''
            INSERT INTO network_events 
            (timestamp, pid, process_name, local_addr, local_port, 
             remote_addr, remote_port, status, protocol, suspicious_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.get('timestamp', time.time()),
            event.get('pid'),
            event.get('process_name'),
            event.get('local_addr'),
            event.get('local_port'),
            event.get('remote_addr'),
            event.get('remote_port'),
            event.get('status'),
            event.get('protocol'),
            event.get('suspicious_score', 0)
        ))
        self.conn.commit()
        return cursor.lastrowid
        
    def insert_file_event(self, event: Dict[str, Any]) -> int:
        """Insert file system event"""
        cursor = self.conn.execute('''
            INSERT INTO file_events (timestamp, event_type, path, process_name, is_suspicious)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            event.get('timestamp', time.time()),
            event['event_type'],
            event['path'],
            event.get('process_name'),
            event.get('is_suspicious', 0)
        ))
        self.conn.commit()
        return cursor.lastrowid
        
    def insert_system_event(self, event: Dict[str, Any]) -> int:
        """Insert system event"""
        cursor = self.conn.execute('''
            INSERT INTO system_events 
            (timestamp, event_type, username, details, success, suspicious_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            event.get('timestamp', time.time()),
            event['event_type'],
            event.get('username'),
            json.dumps(event.get('details', {})),
            event.get('success', True),
            event.get('suspicious_score', 0)
        ))
        self.conn.commit()
        return cursor.lastrowid
        
    def insert_alert(self, alert: Dict[str, Any]) -> int:
        """Insert threat alert"""
        cursor = self.conn.execute('''
            INSERT INTO alerts 
            (timestamp, threat_type, severity, threat_score, source_type, source_id,
             details, ml_confidence, response_actions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alert.get('timestamp', time.time()),
            alert['threat_type'],
            alert['severity'],
            alert['threat_score'],
            alert.get('source_type'),
            alert.get('source_id'),
            json.dumps(alert.get('details', {})),
            alert.get('ml_confidence'),
            json.dumps(alert.get('response_actions', []))
        ))
        self.conn.commit()
        return cursor.lastrowid
        
    def get_recent_alerts(self, hours: int = 24, unresolved_only: bool = False) -> List[Dict]:
        """Get recent alerts"""
        cutoff = time.time() - (hours * 3600)
        query = 'SELECT * FROM alerts WHERE timestamp > ?'
        params = [cutoff]
        
        if unresolved_only:
            query += ' AND resolved = 0'
            
        query += ' ORDER BY timestamp DESC'
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
        
    def get_baseline_stats(self, category: str, metric_name: str) -> Optional[Dict]:
        """Get baseline statistics for a metric"""
        cursor = self.conn.execute('''
            SELECT * FROM baselines WHERE category = ? AND metric_name = ?
        ''', (category, metric_name))
        row = cursor.fetchone()
        return dict(row) if row else None
        
    def update_baseline(self, category: str, metric_name: str, stats: Dict):
        """Update baseline statistics"""
        self.conn.execute('''
            INSERT OR REPLACE INTO baselines
            (category, metric_name, mean_value, std_value, min_value, max_value, 
             sample_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            category,
            metric_name,
            stats.get('mean'),
            stats.get('std'),
            stats.get('min'),
            stats.get('max'),
            stats.get('count'),
            time.time()
        ))
        self.conn.commit()
        
    def is_whitelisted(self, entry_type: str, value: str) -> bool:
        """Check if entry is whitelisted"""
        cursor = self.conn.execute('''
            SELECT COUNT(*) FROM whitelist WHERE entry_type = ? AND value = ?
        ''', (entry_type, value))
        return cursor.fetchone()[0] > 0
        
    def add_whitelist(self, entry_type: str, value: str, reason: str = None):
        """Add whitelist entry"""
        try:
            self.conn.execute('''
                INSERT INTO whitelist (entry_type, value, reason, added_by, added_timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (entry_type, value, reason, 'user', time.time()))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # Already exists
            
    def cleanup_old_events(self, days: int = 30):
        """Remove old events to save space"""
        cutoff = time.time() - (days * 86400)
        
        for table in ['process_events', 'network_events', 'file_events', 'system_events']:
            self.conn.execute(f'DELETE FROM {table} WHERE timestamp < ?', (cutoff,))
            
        self.conn.commit()
        
    def backup_to_nas(self):
        """Backup database to NAS"""
        if self.nas_backup_path:
            try:
                backup_dir = Path(self.nas_backup_path)
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = backup_dir / f"edr_backup_{timestamp}.db"
                
                shutil.copy2(self.db_path, backup_file)
                
                # Keep only last 7 backups
                backups = sorted(backup_dir.glob("edr_backup_*.db"))
                for old_backup in backups[:-7]:
                    old_backup.unlink()
                    
                return True
            except Exception as e:
                print(f"Backup failed: {e}")
                return False
        return False
        
    def get_stats(self) -> Dict:
        """Get database statistics"""
        stats = {}
        
        for table in ['process_events', 'network_events', 'file_events', 
                     'system_events', 'alerts']:
            cursor = self.conn.execute(f'SELECT COUNT(*) FROM {table}')
            stats[f'{table}_count'] = cursor.fetchone()[0]
            
        cursor = self.conn.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0')
        stats['unresolved_alerts'] = cursor.fetchone()[0]
        
        return stats
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
