#!/usr/bin/env python3
"""
Comprehensive test script for EDR system
Tests all major components:
- Configuration validation
- Database operations
- Alerting system
- Process monitoring
"""
import sys
from pathlib import Path
import time

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("  BCAM Hybrid EDR - System Test Suite")
print("=" * 70)
print()

# Test 1: Configuration Validation
print("TEST 1: Configuration Validation")
print("-" * 70)
try:
    from utils.config_validator import validate_config_file, get_validation_summary
    
    config_path = 'config/config.yaml'
    print(f"Validating: {config_path}")
    
    is_valid, errors, warnings = get_validation_summary(config_path)
    
    if warnings:
        print("⚠️  Warnings:")
        for w in warnings:
            print(f"  - {w}")
    
    if errors:
        print("❌ Errors:")
        for e in errors:
            print(f"  - {e}")
        print("FAILED")
        sys.exit(1)
    else:
        config = validate_config_file(config_path)
        print(f"✅ Configuration valid!")
        print(f"   System: {config['system']['name']} v{config['system']['version']}")
        print(f"   Collection interval: {config['collection']['interval']}s")
        print(f"   NAS enabled: {config['nas']['enabled']}")
        
except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)

print()

# Test 2: Database Operations
print("TEST 2: Database Operations")
print("-" * 70)
try:
    from utils.db_v2 import EDRDatabase, ProcessEvent, ValidationError
    
    # Create test database
    test_db_path = 'data/test_edr.db'
    print(f"Creating database: {test_db_path}")
    
    db = EDRDatabase(test_db_path)
    
    # Test valid insert
    print("Testing valid process event insert...")
    event = {
        'pid': 1234,
        'name': 'test_process',
        'cmdline': 'test --arg value',
        'cpu_percent': 25.5,
        'memory_mb': 100.0,
        'num_threads': 5,
        'connections_count': 2,
        'suspicious_score': 35.0,
        'features': {'test': True}
    }
    
    event_id = db.insert_process_event(event)
    if event_id:
        print(f"✅ Event inserted with ID: {event_id}")
    else:
        print("❌ Insert failed")
        sys.exit(1)
    
    # Test invalid insert (should fail validation)
    print("Testing invalid event (should be rejected)...")
    try:
        bad_event = {
            'pid': -1,  # Invalid PID
            'name': 'bad_process'
        }
        db.insert_process_event(bad_event)
        print("❌ Validation should have failed!")
        sys.exit(1)
    except ValidationError:
        print("✅ Invalid event correctly rejected")
    
    # Test stats
    print("Testing database stats...")
    stats = db.get_stats()
    print(f"✅ Stats retrieved:")
    print(f"   Process events: {stats.get('process_events_count', 0)}")
    print(f"   DB size: {stats.get('db_size_mb', 0):.2f}MB")
    
    db.close()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 3: Alerting System
print("TEST 3: Alerting System")
print("-" * 70)
try:
    from utils.alerting import AlertingSystem, Alert, AlertPriority
    
    print("Initializing alerting system...")
    alerter = AlertingSystem(config)
    print("✅ Alerting system initialized")
    
    # Test macOS notification
    print("Sending test macOS notification...")
    test_alert = Alert(
        title="EDR Test Alert",
        message="This is a test of the alerting system",
        priority=AlertPriority.LOW,
        severity="info",
        source="TestSuite"
    )
    
    results = alerter.send_alert(test_alert)
    if results:
        print(f"✅ Alert sent via channels: {list(results.keys())}")
        for channel, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {channel}")
    else:
        print("⚠️  Alert suppressed (rate limit or quiet hours)")
    
    # Test stats
    alert_stats = alerter.get_stats()
    print(f"✅ Alert stats:")
    print(f"   Daily count: {alert_stats['daily_count']}")
    print(f"   Is quiet hours: {alert_stats['is_quiet_hours']}")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: Process Monitor
print("TEST 4: Process Monitor")
print("-" * 70)
try:
    from collectors.process_monitor import ProcessMonitor
    from utils.logger import get_logger
    
    print("Initializing process monitor...")
    logger = get_logger('test', config)
    db = EDRDatabase(test_db_path)
    
    monitor = ProcessMonitor(config, logger, db)
    print("✅ Process monitor initialized")
    
    print("Collecting process data (this may take a few seconds)...")
    events = monitor.collect()
    
    print(f"✅ Collected {len(events)} process events")
    
    # Show top suspicious processes
    suspicious = [e for e in events if e.get('suspicious_score', 0) > 30]
    if suspicious:
        print(f"⚠️  Found {len(suspicious)} suspicious processes:")
        for proc in suspicious[:5]:
            print(f"   - {proc['name']} (PID: {proc['pid']}, Score: {proc['suspicious_score']:.1f})")
    else:
        print("✅ No suspicious processes detected")
    
    db.close()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 5: End-to-End Integration
print("TEST 5: End-to-End Integration")
print("-" * 70)
try:
    print("Testing full collector initialization...")
    from edr_collector_v2 import EDRCollectorV2
    
    # Just initialize, don't start
    collector = EDRCollectorV2('config/config.yaml')
    print("✅ Collector initialized successfully")
    print(f"   Process monitor: {'✅' if collector.process_monitor else '❌'}")
    print(f"   File monitor: {'✅' if collector.file_monitor else '❌'}")
    print(f"   Database: {'✅' if collector.db else '❌'}")
    print(f"   Alerting: {'✅' if collector.alerter else '❌'}")
    
    # Run one collection cycle
    print("Running single collection cycle...")
    collector._collect_cycle()
    print("✅ Collection cycle completed")
    
    # Check stats
    stats = collector.db.get_stats()
    print(f"✅ System stats:")
    print(f"   Events collected: {stats.get('process_events_count', 0)}")
    print(f"   Database size: {stats.get('db_size_mb', 0):.2f}MB")
    
    collector.stop()
    print("✅ Collector stopped gracefully")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 70)
print("  ALL TESTS PASSED! ✅")
print("=" * 70)
print()
print("The EDR system is ready for production use.")
print()
print("Next steps:")
print("  1. Start the collector: python3 edr_collector_v2.py")
print("  2. Start the dashboard: python3 dashboard/app.py")
print("  3. Visit: http://localhost:5000")
print()
