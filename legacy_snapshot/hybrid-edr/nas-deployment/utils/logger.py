"""Logging utility for EDR system with NAS synchronization"""
import logging
import logging.handlers
import json
from pathlib import Path
from typing import Optional
import shutil
from datetime import datetime


class EDRLogger:
    def __init__(self, name: str, log_dir: str, nas_log_dir: Optional[str] = None,
                 level: str = "INFO", max_bytes: int = 10485760, backup_count: int = 5):
        self.name = name
        self.log_dir = Path(log_dir)
        self.nas_log_dir = Path(nas_log_dir) if nas_log_dir else None
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        if self.nas_log_dir:
            self.nas_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        log_file = self.log_dir / f"{name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # JSON structured log handler
        json_log_file = self.log_dir / f"{name}_structured.json"
        json_handler = logging.handlers.RotatingFileHandler(
            json_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(json_handler)
        
    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, extra=kwargs)
        
    def info(self, msg: str, **kwargs):
        self.logger.info(msg, extra=kwargs)
        
    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, extra=kwargs)
        
    def error(self, msg: str, **kwargs):
        self.logger.error(msg, extra=kwargs)
        
    def critical(self, msg: str, **kwargs):
        self.logger.critical(msg, extra=kwargs)
        
    def sync_to_nas(self):
        """Synchronize logs to NAS"""
        if not self.nas_log_dir:
            return False
            
        try:
            # Copy all log files to NAS
            for log_file in self.log_dir.glob("*.log*"):
                dest = self.nas_log_dir / log_file.name
                shutil.copy2(log_file, dest)
                
            for json_file in self.log_dir.glob("*.json*"):
                dest = self.nas_log_dir / json_file.name
                shutil.copy2(json_file, dest)
                
            return True
        except Exception as e:
            self.error(f"Failed to sync logs to NAS: {e}")
            return False


class JSONFormatter(logging.Formatter):
    """Format log records as JSON"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                              'levelname', 'levelno', 'lineno', 'module', 'msecs',
                              'message', 'pathname', 'process', 'processName',
                              'relativeCreated', 'thread', 'threadName']:
                    log_data[key] = value
        
        return json.dumps(log_data)


def get_logger(name: str, config: dict) -> EDRLogger:
    """Factory function to create logger from config"""
    return EDRLogger(
        name=name,
        log_dir=config['paths']['local_logs'],
        nas_log_dir=config['paths'].get('nas_logs'),
        level=config['logging']['level'],
        max_bytes=config['logging']['rotation']['max_bytes'],
        backup_count=config['logging']['rotation']['backup_count']
    )
