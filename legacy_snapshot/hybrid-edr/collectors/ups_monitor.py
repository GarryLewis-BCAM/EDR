"""
UPS Monitor for BCAM EDR - Simple & Robust
Monitors UPS connection status and alerts on disconnect
Note: Battery/power status requires NUT daemon (future enhancement)
"""
import time
import subprocess
from typing import Dict, List, Optional


class UPSMonitor:
    """Monitor APC UPS - Simple connection tracking"""
    
    def __init__(self, config: dict, logger, db):
        self.config = config
        self.logger = logger
        self.db = db
        self.last_status = {}
        self.connection_failures = 0
        self.was_connected = False
        
        # Configuration
        ups_config = config['collection'].get('ups_monitor', {})
        self.enabled = ups_config.get('enabled', True)
        self.poll_interval = ups_config.get('poll_interval', 30)
        
        self.logger.info("UPS Monitor initialized (connection tracking)")
    
    def _check_ups_connection(self) -> Optional[Dict]:
        """Check if UPS is connected via ioreg (fast, reliable)"""
        try:
            result = subprocess.run(
                ['ioreg', '-r', '-c', 'IOUSBDevice', '-l'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode != 0:
                return None
            
            # Look for APC UPS in output
            if 'Back-UPS' in result.stdout or ('051d' in result.stdout.lower() and '0002' in result.stdout.lower()):
                return {
                    'timestamp': time.time(),
                    'connected': True,
                    'vendor': 'APC',
                    'model': 'Back-UPS BX1600MI',
                    'status': 'online',
                    'source': 'ioreg'
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Connection check failed: {e}")
            return None
    
    def collect(self) -> List[Dict]:
        """Collect UPS status"""
        
        if not self.enabled:
            return []
        
        events = []
        
        try:
            status = self._check_ups_connection()
            
            if status:
                # UPS is connected
                self.connection_failures = 0
                
                # Detect reconnection
                if not self.was_connected:
                    self.logger.info("✓ UPS connected")
                    self.was_connected = True
                    
                    # Send reconnection alert if this was a disconnect
                    if self.last_status:
                        events.append({
                            'timestamp': time.time(),
                            'type': 'ups_reconnected',
                            'priority': 'LOW',
                            'title': '✅ UPS Reconnected',
                            'message': 'UPS connection restored',
                            'status': status
                        })
                
                # Create event (robust against missing keys)
                event = {
                    'timestamp': status.get('timestamp', time.time()),
                    'event_type': 'ups_status',
                    'status': status.get('status', 'online'),
                    'battery_charge': None,
                    'runtime_minutes': None,
                    'load_percent': None,
                    'on_battery': False,
                    'low_battery': False,
                    'replace_battery': False,
                    'connected': True,
                    'device_name': status.get('model', 'Unknown'),
                    'alert_triggered': len(events) > 0
                }
                
                self.db.insert_ups_event(event)
                events.append(event)
                self.last_status = status
                
            else:
                # UPS not detected
                self.connection_failures += 1
                
                # Alert on disconnect
                if self.was_connected:
                    self.logger.warning("⚠️ UPS disconnected!")
                    self.was_connected = False
                    
                    events.append({
                        'timestamp': time.time(),
                        'type': 'ups_disconnected',
                        'priority': 'HIGH',
                        'title': '⚠️ UPS Disconnected',
                        'message': 'UPS no longer detected on USB. Check cable connection.',
                        'status': {'connected': False}
                    })
                    
                    # Log disconnect event
                    event = {
                        'timestamp': time.time(),
                        'event_type': 'ups_disconnected',
                        'status': 'disconnected',
                        'battery_charge': None,
                        'runtime_minutes': None,
                        'load_percent': None,
                        'on_battery': False,
                        'low_battery': False,
                        'replace_battery': False,
                        'connected': False,
                        'device_name': 'Unknown',
                        'alert_triggered': True
                    }
                    self.db.insert_ups_event(event)
                    events.append(event)
                    
        except Exception as e:
            self.logger.error(f"UPS collection error: {e}")
        
        return events
    
    def get_status(self) -> Dict:
        """Get current UPS status"""
        status = self._check_ups_connection()
        if status:
            return status
        
        return {
            'connected': False,
            'status': 'disconnected',
            'message': 'UPS not connected or not detected'
        }
