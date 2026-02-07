#!/bin/bash
# Robust EDR Collector Startup Script
# Auto-starts with proper virtual environment

cd "$(dirname "$0")"
EDR_DIR="/Users/garrylewis/Security/hybrid-edr"

# Kill any existing collector
pkill -f "edr_collector_v2.py" 2>/dev/null

# Wait a moment
sleep 2

# Start with venv Python
cd "$EDR_DIR"
source venv/bin/activate
nohup python3 edr_collector_v2.py > /tmp/edr_collector.log 2>&1 &
COLLECTOR_PID=$!

# Wait and verify
sleep 3
if ps -p $COLLECTOR_PID > /dev/null 2>&1; then
    echo "✅ EDR Collector started successfully (PID: $COLLECTOR_PID)"
    echo $COLLECTOR_PID > /tmp/edr_collector.pid
else
    echo "❌ EDR Collector failed to start"
    tail -20 logs/edr_collector_v2.log | grep ERROR
    exit 1
fi
