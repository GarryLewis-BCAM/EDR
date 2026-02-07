#!/usr/bin/env python3
"""Main EDR Collector Daemon - BCAM Security"""
import sys
import time
import yaml
import signal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.db import EDRDatabase
from utils.logger import get_logger
from collectors.process_monitor import ProcessMonitor
from collectors.file_monitor import FileMonitor


class EDRCollector:
    def __init__(self, config_path: str):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize logger
        self.logger = get_logger('edr_collector', self.config)
        self.logger.info("=" * 60)
        self.logger.info("BCAM Hybrid EDR System Starting")
        self.logger.info("=" * 60)
        
        # Initialize database
        self.db = EDRDatabase(
            db_path=self.config['paths']['database'],
            nas_backup_path=self.config['paths'].get('nas_backups')
        )
        self.logger.info(f"Database initialized: {self.config['paths']['database']}")
        
        # Initialize monitors
        self.process_monitor = ProcessMonitor(self.config, self.logger, self.db)
        self.file_monitor = FileMonitor(self.config, self.logger, self.db)
        
        # State
        self.running = False
        self.collection_count = 0
        self.start_time = time.time()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        
    def start(self):
        """Start all monitoring"""
        self.running = True
        
        # Start file monitor
        if self.config['collection']['file_monitor']['enabled']:
            self.file_monitor.start()
            self.logger.info("✓ File monitor started")
        
        self.logger.info(f"✓ Collection interval: {self.config['collection']['interval']}s")
        self.logger.info("✓ EDR system is now active")
        self.logger.info("")
        
        # Main collection loop
        try:
            while self.running:
                self._collect_cycle()
                time.sleep(self.config['collection']['interval'])
                
        except Exception as e:
            self.logger.error(f"Fatal error in collection loop: {e}", exc_info=True)
            self.stop()
    
    def _collect_cycle(self):
        """Single collection cycle"""
        cycle_start = time.time()
        
        try:
            # Collect process data
            if self.config['collection']['process_monitor']['enabled']:
                process_events = self.process_monitor.collect()
                
            self.collection_count += 1
            
            # Periodic maintenance
            if self.collection_count % 100 == 0:
                self._periodic_maintenance()
            
            # Log status every 100 cycles (~8 minutes at 5s interval)
            if self.collection_count % 100 == 0:
                uptime = time.time() - self.start_time
                stats = self.db.get_stats()
                self.logger.info(
                    f"Status: {self.collection_count} cycles, "
                    f"uptime: {uptime/3600:.1f}h, "
                    f"events: {stats.get('process_events_count', 0)}, "
                    f"alerts: {stats.get('unresolved_alerts', 0)} unresolved"
                )
            
            cycle_time = time.time() - cycle_start
            if cycle_time > self.config['collection']['interval']:
                self.logger.warning(f"Collection cycle took {cycle_time:.2f}s (longer than interval)")
                
        except Exception as e:
            self.logger.error(f"Error in collection cycle: {e}", exc_info=True)
    
    def _periodic_maintenance(self):
        """Periodic maintenance tasks"""
        try:
            # Sync logs to NAS
            if self.config['nas']['enabled']:
                self.logger.sync_to_nas()
            
            # Backup database to NAS
            if self.collection_count % 1000 == 0:  # Every ~1.4 hours
                if self.db.backup_to_nas():
                    self.logger.info("✓ Database backed up to NAS")
            
            # Cleanup old events
            if self.collection_count % 10000 == 0:  # Every ~14 hours
                days = self.config['maintenance']['auto_cleanup']['old_events_days']
                self.db.cleanup_old_events(days)
                self.logger.info(f"✓ Cleaned up events older than {days} days")
                
        except Exception as e:
            self.logger.error(f"Maintenance task failed: {e}")
    
    def stop(self):
        """Stop all monitoring"""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping EDR system...")
        
        # Stop file monitor
        if self.file_monitor:
            self.file_monitor.stop()
            self.logger.info("✓ File monitor stopped")
        
        # Final sync and backup
        if self.config['nas']['enabled']:
            self.logger.sync_to_nas()
            self.db.backup_to_nas()
            self.logger.info("✓ Final sync to NAS completed")
        
        # Close database
        self.db.close()
        self.logger.info("✓ Database closed")
        
        # Final stats
        uptime = time.time() - self.start_time
        stats = self.db.get_stats()
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("EDR System Shutdown Summary")
        self.logger.info("=" * 60)
        self.logger.info(f"Total runtime: {uptime/3600:.2f} hours")
        self.logger.info(f"Collection cycles: {self.collection_count}")
        self.logger.info(f"Process events: {stats.get('process_events_count', 0)}")
        self.logger.info(f"File events: {stats.get('file_events_count', 0)}")
        self.logger.info(f"Network events: {stats.get('network_events_count', 0)}")
        self.logger.info(f"Alerts generated: {stats.get('alerts_count', 0)}")
        self.logger.info("=" * 60)


def main():
    """Main entry point"""
    config_path = Path(__file__).parent / 'config' / 'config.yaml'
    
    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}")
        sys.exit(1)
    
    collector = EDRCollector(str(config_path))
    
    try:
        collector.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        collector.stop()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
