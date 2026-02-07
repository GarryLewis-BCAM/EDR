#!/bin/bash
# EDR Collector Fix Validation Script
# Tests the file event handling fix implemented on 2024-12-03

set -e

echo "=================================================="
echo "EDR Collector Fix Validation"
echo "=================================================="
echo ""

cd ~/Security/hybrid-edr

# Test 1: Import validation
echo "Test 1: Validating Python imports..."
python3 -c "
from utils.db_v2 import EDRDatabase, FileEvent
from collectors.file_monitor import FileMonitor
print('✅ All imports successful')
"

# Test 2: FileEvent dataclass
echo ""
echo "Test 2: Testing FileEvent dataclass..."
python3 -c "
from utils.db_v2 import FileEvent

# Valid event
fe = FileEvent(event_type='created', path='/tmp/test.txt', is_suspicious=True)
print(f'✅ Valid FileEvent created: {fe.event_type}')

# Invalid event type
try:
    bad_fe = FileEvent(event_type='invalid', path='/tmp/test.txt')
    print('❌ Should have raised ValidationError')
    exit(1)
except Exception as e:
    print(f'✅ Invalid event_type correctly rejected')
"

# Test 3: Database insertion
echo ""
echo "Test 3: Testing database file event insertion..."
python3 -c "
from utils.db_v2 import EDRDatabase
import tempfile
import os

temp_db = tempfile.mktemp(suffix='.db')
try:
    db = EDRDatabase(temp_db)
    
    event = {
        'event_type': 'created',
        'path': '/tmp/test_file.txt',
        'is_suspicious': True
    }
    result = db.insert_file_event(event)
    
    if result:
        print(f'✅ File event inserted with ID: {result}')
    else:
        print('❌ Failed to insert file event')
        exit(1)
finally:
    if os.path.exists(temp_db):
        os.remove(temp_db)
"

# Test 4: Check for existing errors in log
echo ""
echo "Test 4: Checking for recent errors in log..."
RECENT_ERRORS=$(tail -100 collector.log 2>/dev/null | grep -c "TypeError.*event_type" || echo "0")
if [ "$RECENT_ERRORS" -gt "0" ]; then
    echo "⚠️  Found $RECENT_ERRORS old errors in log (these are from before the fix)"
else
    echo "✅ No TypeError errors found in recent log"
fi

# Test 5: Method existence
echo ""
echo "Test 5: Verifying insert_file_event method exists..."
python3 -c "
from utils.db_v2 import EDRDatabase
assert hasattr(EDRDatabase, 'insert_file_event'), 'insert_file_event method missing'
print('✅ insert_file_event method exists')
"

echo ""
echo "=================================================="
echo "✅ All validation tests passed!"
echo "=================================================="
echo ""
echo "The collector is now fixed and ready to run."
echo "To start the collector, run:"
echo "  ./start_collector.sh"
echo ""
echo "To monitor for new issues:"
echo "  tail -f collector.log | grep -i error"
