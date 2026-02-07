#!/bin/bash
#
# BCAM EDR Health Check Script
# Verifies collector and network tracker are running properly
#

EDR_DIR="/Users/garrylewis/Security/hybrid-edr"
COLLECTOR_LOG="$EDR_DIR/logs/collector.out"
DASHBOARD_PORT=5050

echo "🏥 BCAM EDR Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Component status tracking
ALL_HEALTHY=true

# ============================================================
# CHECK COLLECTOR
# ============================================================

echo "🔍 Checking Collector..."
COLLECTOR_PID=$(pgrep -f "python.*edr_collector_v2.py" || echo "")

if [ -z "$COLLECTOR_PID" ]; then
    echo "  ❌ Status: NOT RUNNING"
    ALL_HEALTHY=false
else
    echo "  ✅ Status: Running (PID: $COLLECTOR_PID)"
    
    # Check if process is responsive
    if ps -p "$COLLECTOR_PID" > /dev/null 2>&1; then
        echo "  ✅ Process: Healthy"
        
        # Check recent activity in log
        if [ -f "$COLLECTOR_LOG" ]; then
            LAST_LOG_TIME=$(stat -f "%m" "$COLLECTOR_LOG" 2>/dev/null || echo "0")
            CURRENT_TIME=$(date +%s)
            TIME_DIFF=$((CURRENT_TIME - LAST_LOG_TIME))
            
            if [ "$TIME_DIFF" -lt 120 ]; then
                echo "  ✅ Activity: Recent (${TIME_DIFF}s ago)"
            else
                echo "  ⚠️  Activity: Stale (${TIME_DIFF}s ago)"
            fi
        fi
    else
        echo "  ❌ Process: Zombie/Unresponsive"
        ALL_HEALTHY=false
    fi
fi

echo ""

# ============================================================
# CHECK NETWORK TRACKER
# ============================================================

echo "📡 Checking Network Tracker..."

if [ -z "$COLLECTOR_PID" ]; then
    echo "  ⏭️  Skipped (collector not running)"
else
    # Network tracker is part of collector, check if it initialized
    if [ -f "$COLLECTOR_LOG" ]; then
        if tail -100 "$COLLECTOR_LOG" 2>/dev/null | grep -q "Network tracker initialized"; then
            echo "  ✅ Status: Initialized"
            
            # Check for recent network collection activity
            if tail -50 "$COLLECTOR_LOG" 2>/dev/null | grep -q "network collection\|Collected.*network"; then
                echo "  ✅ Activity: Collecting data"
            else
                # Check for fallback mode
                if tail -50 "$COLLECTOR_LOG" 2>/dev/null | grep -q "per-process enumeration\|fallback"; then
                    echo "  ⚠️  Mode: Fallback (per-process iteration)"
                else
                    echo "  ⚠️  Activity: No recent data (may be waiting for collection cycle)"
                fi
            fi
        else
            echo "  ❌ Status: Not initialized"
            echo "  💡 Check collector log for initialization errors"
            ALL_HEALTHY=false
        fi
    else
        echo "  ⚠️  Cannot verify (no log file)"
        ALL_HEALTHY=false
    fi
fi

echo ""

# ============================================================
# CHECK DASHBOARD
# ============================================================

echo "🌐 Checking Dashboard..."

if lsof -ti:$DASHBOARD_PORT > /dev/null 2>&1; then
    DASHBOARD_PID=$(lsof -ti:$DASHBOARD_PORT)
    echo "  ✅ Status: Running (PID: $DASHBOARD_PID)"
    echo "  ✅ Port: $DASHBOARD_PORT (listening)"
    
    # Check if it's responding to HTTP requests
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$DASHBOARD_PORT" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
        echo "  ✅ HTTP: Responding (${HTTP_CODE})"
    else
        echo "  ⚠️  HTTP: Not responding properly (${HTTP_CODE})"
    fi
else
    echo "  ❌ Status: NOT RUNNING"
    echo "  ❌ Port: $DASHBOARD_PORT (not listening)"
    ALL_HEALTHY=false
fi

echo ""

# ============================================================
# CHECK NAS MOUNTS
# ============================================================

echo "📁 Checking NAS Mounts..."

NAS_SHARES=("Apps" "Data" "Docker")
MOUNTED_COUNT=0

for share in "${NAS_SHARES[@]}"; do
    if [ -d "/Volumes/$share" ]; then
        echo "  ✅ $share: Mounted"
        ((MOUNTED_COUNT++))
    else
        echo "  ⚠️  $share: Not mounted"
    fi
done

if [ $MOUNTED_COUNT -eq 0 ]; then
    echo "  ⚠️  No NAS shares mounted (EDR will use local storage only)"
fi

echo ""

# ============================================================
# SUMMARY
# ============================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$ALL_HEALTHY" = true ]; then
    echo "✅ Overall Status: HEALTHY"
    echo ""
    echo "All critical components are running properly."
    exit 0
else
    echo "⚠️  Overall Status: DEGRADED"
    echo ""
    echo "Some components are not running properly."
    echo "💡 To restart: $EDR_DIR/launch_edr.sh"
    echo "💡 View logs: tail -f $COLLECTOR_LOG"
    exit 1
fi
