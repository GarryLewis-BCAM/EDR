#!/bin/bash
# Quick EDR system status check

cd "$(dirname "$0")"

echo "============================================================"
echo "  BCAM Hybrid EDR System - Status Check"
echo "============================================================"
echo ""

# Check if collector is running
if pgrep -f "edr_collector_v2.py" > /dev/null; then
    echo "✅ Collector: RUNNING (PID: $(pgrep -f 'edr_collector_v2.py'))"
else
    echo "❌ Collector: NOT RUNNING"
fi

# Check if dashboard is running
if pgrep -f "dashboard/app.py" > /dev/null; then
    echo "✅ Dashboard: RUNNING (PID: $(pgrep -f 'dashboard/app.py'))"
    echo "   Visit: http://localhost:5000"
else
    echo "❌ Dashboard: NOT RUNNING"
fi

echo ""

# Check database
if [ -f "data/edr.db" ]; then
    DB_SIZE=$(du -h data/edr.db | cut -f1)
    EVENT_COUNT=$(sqlite3 data/edr.db "SELECT COUNT(*) FROM process_events;" 2>/dev/null || echo "0")
    ALERT_COUNT=$(sqlite3 data/edr.db "SELECT COUNT(*) FROM alerts;" 2>/dev/null || echo "0")
    SUSPICIOUS=$(sqlite3 data/edr.db "SELECT COUNT(*) FROM process_events WHERE suspicious_score > 50;" 2>/dev/null || echo "0")
    
    echo "📊 Database Stats:"
    echo "   Size: $DB_SIZE"
    echo "   Process events: $EVENT_COUNT"
    echo "   Alerts: $ALERT_COUNT"
    echo "   Suspicious (>50): $SUSPICIOUS"
else
    echo "⚠️  Database not found: data/edr.db"
fi

echo ""

# Check recent logs
if [ -f "logs/edr_collector_v2.log" ]; then
    LAST_LOG=$(tail -1 logs/edr_collector_v2.log 2>/dev/null)
    echo "📝 Latest log entry:"
    echo "   $LAST_LOG"
    
    ERROR_COUNT=$(grep -c "ERROR" logs/edr_collector_v2.log 2>/dev/null || echo "0")
    echo ""
    echo "   Error count (today): $ERROR_COUNT"
else
    echo "⚠️  Log file not found"
fi

echo ""

# Check NAS mount
if [ -d "/Volumes/Apps/Services/EDR" ]; then
    echo "✅ NAS: MOUNTED (/Volumes/Apps/Services/EDR)"
else
    echo "⚠️  NAS: NOT MOUNTED"
fi

echo ""
echo "============================================================"
echo ""

# Provide quick actions
echo "Quick Actions:"
echo "  View logs:      tail -f logs/edr_collector_v2.log"
echo "  Start collector: python3 edr_collector_v2.py"
echo "  Start dashboard: ./start_dashboard.sh"
echo "  Run tests:      python3 test_system.py"
echo ""
