#!/usr/bin/env python3
"""
Quick test script for UPS monitoring
Verifies USB connection and displays current UPS status
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from collectors.ups_monitor import UPSMonitor
from utils.logger import get_logger
from utils.db_v2 import EDRDatabase
from utils.config_validator import validate_config_file

def main():
    print("=" * 60)
    print("BCAM EDR - UPS Monitor Test")
    print("=" * 60)
    print()
    
    # Load config
    print("Loading configuration...")
    config = validate_config_file('config/config.yaml')
    print("✓ Config loaded\n")
    
    # Initialize components
    logger = get_logger('ups_test', config)
    db = EDRDatabase(config['paths']['database'])
    
    # Create UPS monitor
    print("Initializing UPS monitor...")
    ups_monitor = UPSMonitor(config, logger, db)
    print("✓ UPS monitor initialized\n")
    
    # Get current status
    print("Reading UPS status...")
    status = ups_monitor.get_status()
    
    print("\nCurrent UPS Status:")
    print("-" * 60)
    print(f"Connected:       {status.get('connected', False)}")
    print(f"Device:          {status.get('model', 'Unknown')}")
    print(f"Status:          {status.get('status', 'unknown')}")
    print(f"Battery Charge:  {status.get('battery_charge', 'N/A')}")
    print(f"Runtime:         {status.get('runtime_minutes', 'N/A')} minutes")
    print(f"Load:            {status.get('load_percent', 'N/A')}%")
    print(f"On Battery:      {status.get('on_battery', False)}")
    print(f"Low Battery:     {status.get('low_battery', False)}")
    print(f"Replace Battery: {status.get('replace_battery', False)}")
    print(f"Data Source:     {status.get('source', 'unknown')}")
    print("-" * 60)
    print()
    
    # Check database
    print("Checking UPS events in database...")
    events_count = db._get_connection().execute(
        "SELECT COUNT(*) FROM ups_events"
    ).fetchone()[0]
    print(f"✓ Total UPS events logged: {events_count}")
    
    # Show last 3 events
    if events_count > 0:
        print("\nLast 3 UPS events:")
        cursor = db._get_connection().execute("""
            SELECT datetime(timestamp, 'unixepoch', 'localtime') as time, 
                   event_type, status, on_battery, connected
            FROM ups_events 
            ORDER BY timestamp DESC 
            LIMIT 3
        """)
        for row in cursor:
            print(f"  {row[0]} - {row[1]} - status:{row[2]} battery:{row[3]} connected:{row[4]}")
    
    print()
    print("=" * 60)
    print("UPS Monitor Test Complete!")
    print("=" * 60)
    
    # Alert configuration check
    print("\nAlert Configuration:")
    ups_config = config['collection'].get('ups_monitor', {})
    print(f"  Enabled:            {ups_config.get('enabled', False)}")
    print(f"  Poll Interval:      {ups_config.get('poll_interval', 30)}s")
    print(f"  Warning Threshold:  {ups_config.get('battery_thresholds', {}).get('warning', 50)}%")
    print(f"  Critical Threshold: {ups_config.get('battery_thresholds', {}).get('critical', 20)}%")
    print()
    
    # SMS configuration check
    sms_config = config['alerts']['channels'].get('twilio_sms', {})
    if sms_config.get('enabled'):
        print("✓ Twilio SMS alerts ENABLED")
        print(f"  Phone:      {sms_config.get('to_numbers', [])[0] if sms_config.get('to_numbers') else 'Not configured'}")
        print(f"  Min Severity: {sms_config.get('min_severity', 'high')}")
    else:
        print("⚠ Twilio SMS alerts DISABLED")
    
    db.close()

if __name__ == '__main__':
    main()
