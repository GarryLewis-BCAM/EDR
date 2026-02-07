#!/bin/bash
#
# Restart Collector with Clean Cache
# Prevents Python bytecode cache issues
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "  Restarting EDR Collector (Clean)"
echo "================================================"
echo ""

# Step 1: Stop existing collector
echo "1. Stopping existing collector..."
pkill -f "edr_collector" || echo "   No collector running"
sleep 2

# Step 2: Clear Python cache (prevents .pyc issues)
echo "2. Clearing Python bytecode cache..."
find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR" -name "*.pyc" -delete 2>/dev/null || true
echo "   ✓ Cache cleared"

# Step 3: Verify critical files exist
echo "3. Verifying critical files..."
critical_files=(
    "edr_collector_v2.py"
    "collectors/file_monitor.py"
    "collectors/network_tracker.py"
    "collectors/process_monitor.py"
    "utils/db_v2.py"
)

for file in "${critical_files[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$file" ]; then
        echo "   ❌ CRITICAL: Missing $file"
        exit 1
    fi
done
echo "   ✓ All critical files present"

# Step 4: Start collector fresh
echo "4. Starting collector..."
cd "$SCRIPT_DIR"
nohup python3 edr_collector_v2.py > collector_startup.log 2>&1 &
COLLECTOR_PID=$!

sleep 3

# Step 5: Verify startup
echo "5. Verifying startup..."
if ps -p $COLLECTOR_PID > /dev/null; then
    echo "   ✓ Collector running (PID: $COLLECTOR_PID)"
    
    # Check for immediate errors
    if grep -q "ERROR\|CRITICAL\|Traceback" collector_startup.log 2>/dev/null; then
        echo "   ⚠️  WARNING: Errors detected in startup log"
        echo ""
        echo "Last 10 lines of log:"
        tail -10 collector_startup.log
        echo ""
        echo "Full log: $SCRIPT_DIR/collector_startup.log"
    else
        echo "   ✓ No errors in startup"
    fi
else
    echo "   ❌ FAILED: Collector not running"
    echo ""
    echo "Startup log:"
    cat collector_startup.log
    exit 1
fi

echo ""
echo "================================================"
echo "  Collector Restarted Successfully"
echo "================================================"
echo ""
echo "Monitor logs:"
echo "  tail -f $SCRIPT_DIR/collector.log"
echo ""
echo "Startup log:"
echo "  cat $SCRIPT_DIR/collector_startup.log"
echo ""
