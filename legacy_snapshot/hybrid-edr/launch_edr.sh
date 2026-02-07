#!/bin/bash
#
# BCAM EDR Complete Launcher - Robust Version
# Mounts NAS, starts collector & dashboard with health checks
#

set -e  # Exit on error

EDR_DIR="/Users/garrylewis/Security/hybrid-edr"
LOG_DIR="$EDR_DIR/logs"
VENV_PYTHON="$EDR_DIR/venv/bin/python3"
COLLECTOR_SCRIPT="$EDR_DIR/edr_collector_v2.py"
DASHBOARD_SCRIPT="$EDR_DIR/dashboard/app.py"
COLLECTOR_LOG="$LOG_DIR/collector.out"
DASHBOARD_PORT=5050

cd "$EDR_DIR"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

echo "🚀 Starting BCAM EDR System..."
echo ""

# ============================================================
# PRE-FLIGHT CHECKS
# ============================================================

echo "🔍 Pre-flight checks..."

# Check venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ ERROR: Virtual environment not found at $VENV_PYTHON"
    echo "💡 Please run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Check critical dependencies
if ! "$VENV_PYTHON" -c "import watchdog, psutil, flask" 2>/dev/null; then
    echo "⚠️  Missing dependencies, installing..."
    "$EDR_DIR/venv/bin/pip" install -q -r requirements.txt || {
        echo "❌ ERROR: Failed to install dependencies"
        exit 1
    }
    echo "✅ Dependencies installed"
fi

# Check config exists
if [ ! -f "$EDR_DIR/config/config.yaml" ]; then
    echo "❌ ERROR: config.yaml not found at $EDR_DIR/config/config.yaml"
    exit 1
fi

echo "✅ Pre-flight checks passed"
echo ""

# ============================================================
# MOUNT NAS
# ============================================================

echo "📁 Mounting NAS..."
if [ -f "$EDR_DIR/mount_nas.sh" ]; then
    "$EDR_DIR/mount_nas.sh" || echo "⚠️  NAS mount failed (non-fatal)"
else
    echo "⚠️  mount_nas.sh not found, skipping"
fi
echo ""

# ============================================================
# START COLLECTOR (includes network tracker)
# ============================================================

echo "🔧 Checking collector status..."

COLLECTOR_PID=$(pgrep -f "python.*edr_collector_v2.py" || echo "")

if [ -n "$COLLECTOR_PID" ]; then
    echo "✅ Collector already running (PID: $COLLECTOR_PID)"
    # Verify it's actually responsive
    if ps -p "$COLLECTOR_PID" > /dev/null 2>&1; then
        echo "✅ Collector process is healthy"
    else
        echo "⚠️  Collector PID exists but process is zombie, restarting..."
        kill -9 "$COLLECTOR_PID" 2>/dev/null || true
        sleep 1
        COLLECTOR_PID=""
    fi
fi

if [ -z "$COLLECTOR_PID" ]; then
    echo "⏳ Starting collector (includes network tracker)..."
    
    # Kill any stale processes
    pkill -9 -f "edr_collector_v2.py" 2>/dev/null || true
    sleep 1
    
    # Start collector with proper environment
    nohup "$VENV_PYTHON" "$COLLECTOR_SCRIPT" > "$COLLECTOR_LOG" 2>&1 &
    COLLECTOR_PID=$!
    
    echo "⏳ Collector starting (PID: $COLLECTOR_PID)..."
    
    # Wait for collector to initialize (up to 10 seconds)
    for i in {1..10}; do
        if ps -p "$COLLECTOR_PID" > /dev/null 2>&1; then
            # Check if it's actually running (look for activity in log)
            if tail -5 "$COLLECTOR_LOG" 2>/dev/null | grep -q "EDR system is now ACTIVE\|Network tracker initialized\|Collector started"; then
                echo "✅ Collector started successfully (PID: $COLLECTOR_PID)"
                break
            fi
        else
            echo "❌ ERROR: Collector failed to start"
            echo "📄 Last 20 lines of collector log:"
            tail -20 "$COLLECTOR_LOG" 2>/dev/null || echo "No log available"
            exit 1
        fi
        sleep 1
    done
    
    # Final verification
    if ! ps -p "$COLLECTOR_PID" > /dev/null 2>&1; then
        echo "❌ ERROR: Collector process died"
        echo "📄 Last 20 lines of collector log:"
        tail -20 "$COLLECTOR_LOG" 2>/dev/null || echo "No log available"
        exit 1
    fi
fi

echo ""

# ============================================================
# START DASHBOARD
# ============================================================

echo "🌐 Checking dashboard status..."

if lsof -ti:$DASHBOARD_PORT > /dev/null 2>&1; then
    DASHBOARD_PID=$(lsof -ti:$DASHBOARD_PORT)
    echo "✅ Dashboard already running on port $DASHBOARD_PORT (PID: $DASHBOARD_PID)"
else
    echo "⏳ Starting dashboard..."
    
    # Start dashboard in background
    nohup "$VENV_PYTHON" "$DASHBOARD_SCRIPT" > "$LOG_DIR/dashboard.out" 2>&1 &
    DASHBOARD_PID=$!
    
    # Wait for dashboard to be ready (up to 10 seconds)
    echo "⏳ Dashboard starting (PID: $DASHBOARD_PID)..."
    for i in {1..10}; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$DASHBOARD_PORT" | grep -q "200\|302"; then
            echo "✅ Dashboard started successfully (PID: $DASHBOARD_PID)"
            break
        fi
        if ! ps -p "$DASHBOARD_PID" > /dev/null 2>&1; then
            echo "❌ ERROR: Dashboard failed to start"
            echo "📄 Last 20 lines of dashboard log:"
            tail -20 "$LOG_DIR/dashboard.out" 2>/dev/null || echo "No log available"
            exit 1
        fi
        sleep 1
    done
fi

echo ""

# ============================================================
# VERIFY COMPONENTS
# ============================================================

echo "✓ Verifying components..."

# Verify collector is running
if ! pgrep -f "python.*edr_collector_v2.py" > /dev/null; then
    echo "❌ ERROR: Collector not running after startup"
    exit 1
fi

# Verify network tracker is active (check collector log)
if tail -50 "$COLLECTOR_LOG" 2>/dev/null | grep -q "Network tracker initialized"; then
    echo "✅ Network tracker: active"
else
    echo "⚠️  Network tracker: status unknown (check logs)"
fi

# Verify dashboard is responding
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$DASHBOARD_PORT" | grep -q "200\|302"; then
    echo "✅ Dashboard: responding on port $DASHBOARD_PORT"
else
    echo "⚠️  Dashboard: not responding (may still be starting)"
fi

echo ""

# ============================================================
# OPEN BROWSER
# ============================================================

echo "🌐 Opening dashboard in browser..."
sleep 1
open "http://localhost:$DASHBOARD_PORT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ BCAM EDR System Ready!"
echo ""
echo "   📊 Dashboard:       http://localhost:$DASHBOARD_PORT"
echo "   🔍 Collector:       Running (PID: $(pgrep -f 'python.*edr_collector_v2.py'))"
echo "   📡 Network Tracker: Active (part of collector)"
echo ""
echo "   📄 Logs:"
echo "      Collector: $COLLECTOR_LOG"
echo "      Dashboard: $LOG_DIR/dashboard.out"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 To view collector logs: tail -f $COLLECTOR_LOG"
echo "💡 To stop: pkill -f 'edr_collector_v2.py' && pkill -f 'dashboard/app.py'"
echo ""
