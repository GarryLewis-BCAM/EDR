"""File system monitoring collector"""
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from typing import Dict, List
import fnmatch


class FileMonitor:
    def __init__(self, config: dict, logger, db):
        self.config = config
        self.logger = logger
        self.db = db
        self.monitored_dirs = config['paths']['monitored_dirs']
        self.ignore_patterns = config['collection']['file_monitor']['ignore_patterns']
        self.observers = []
        self.events_buffer = []
        
    def start(self):
        """Start monitoring file system"""
        handler = FileEventHandler(self)
        
        for directory in self.monitored_dirs:
            if Path(directory).exists():
                observer = Observer()
                observer.schedule(handler, directory, recursive=True)
                observer.start()
                self.observers.append(observer)
                self.logger.info(f"Started monitoring: {directory}")
        
    def stop(self):
        """Stop all observers"""
        for observer in self.observers:
            observer.stop()
            observer.join()
    
    def should_ignore(self, path: str) -> bool:
        """Check if file should be ignored"""
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
    
    def handle_event(self, event_type: str, path: str):
        """Process file system event"""
        if self.should_ignore(path):
            return
        
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'path': path,
            'is_suspicious': self._is_suspicious(path, event_type)
        }
        
        self.events_buffer.append(event)
        self.db.insert_file_event(event)  # Fixed: use insert_file_event instead of insert_process_event
        
        if event['is_suspicious']:
            self.logger.warning(f"Suspicious file activity: {event_type} on {path}")
    
    def _is_suspicious(self, path: str, event_type: str) -> bool:
        """Determine if file activity is suspicious"""
        path_lower = path.lower()
        
        # Suspicious file extensions
        suspicious_extensions = ['.sh', '.command', '.app', '.dmg', '.pkg', '.dylib']
        if any(path_lower.endswith(ext) for ext in suspicious_extensions):
            if event_type in ['created', 'modified']:
                return True
        
        # Suspicious locations
        suspicious_paths = ['/tmp/', '/var/tmp/', '/.', '/private/tmp/']
        if any(suspicious in path_lower for suspicious in suspicious_paths):
            return True
        
        return False


class FileEventHandler(FileSystemEventHandler):
    def __init__(self, monitor):
        self.monitor = monitor
    
    def on_created(self, event):
        if not event.is_directory:
            self.monitor.handle_event('created', event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.monitor.handle_event('modified', event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.monitor.handle_event('deleted', event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self.monitor.handle_event('moved', f"{event.src_path} -> {event.dest_path}")
