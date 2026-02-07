#!/usr/bin/env python3
"""
Test macOS Native Network Tracker
Demonstrates full system-wide network visibility without root
"""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from collectors.network_tracker_macos_native import MacOSNativeNetworkTracker
import logging

# Simple logger for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test')

# Mock config
config = {
    'paths': {
        'database': 'test.db'
    }
}

# Mock database
class MockDB:
    def insert_network_event(self, event):
        pass

print("=" * 60)
print("  Testing macOS Native Network Tracker")
print("  Using lsof for full system-wide visibility")
print("=" * 60)
print()

# Create tracker
tracker = MacOSNativeNetworkTracker(config, logger, MockDB())

# Collect connections
print("Collecting network connections...")
events = tracker.collect()

print(f"\n✅ Collected {len(events)} network connections\n")

if events:
    print("Sample connections:")
    print("-" * 80)
    for i, event in enumerate(events[:10]):  # Show first 10
        print(f"{i+1}. {event['process_name']:20} (PID {event['process_pid']:6}) → "
              f"{event['dest_ip']:15}:{event['dest_port']:5} "
              f"[{event['protocol']:4}] Score: {event['threat_score']:.0f}")
    
    if len(events) > 10:
        print(f"\n... and {len(events) - 10} more connections")
    
    print("-" * 80)
    
    # Show high-threat connections
    suspicious = [e for e in events if e['threat_score'] > 50]
    if suspicious:
        print(f"\n⚠️  {len(suspicious)} suspicious connections detected:")
        for event in suspicious:
            print(f"   • {event['process_name']} → {event['dest_ip']}:{event['dest_port']} "
                  f"(Score: {event['threat_score']:.0f})")
    else:
        print("\n✅ No suspicious connections detected")
else:
    print("⚠️  No network connections found")
    print("   This might be normal if no applications are currently connected")

# Test listening ports
print("\n" + "=" * 60)
print("Testing listening ports detection...")
listening = tracker.get_listening_ports()
print(f"✅ Found {len(listening)} listening ports\n")

if listening:
    print("Listening ports:")
    print("-" * 80)
    for port in listening[:20]:  # Show first 20
        print(f"   {port['ip']:20} : {port['port']:6} ({port['protocol']})")
    if len(listening) > 20:
        print(f"   ... and {len(listening) - 20} more")

# Test connection stats
print("\n" + "=" * 60)
print("Testing connection statistics...")
stats = tracker.get_connection_stats()
if stats:
    print("✅ Connection statistics retrieved:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
else:
    print("⚠️  Could not retrieve connection statistics")

print("\n" + "=" * 60)
print("✅ Test completed successfully!")
print("=" * 60)
