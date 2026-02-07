#!/bin/bash
# EDR Collector Startup Script
# This ensures the collector runs with the correct Python environment

EDR_DIR="/Users/garrylewis/Security/hybrid-edr"
VENV_PYTHON="$EDR_DIR/venv/bin/python3"
COLLECTOR_SCRIPT="$EDR_DIR/edr_collector_v2.py"

cd "$EDR_DIR"

# Check if venv Python exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment Python not found at $VENV_PYTHON"
    echo "Please run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Check if requirements are installed
if ! "$VENV_PYTHON" -c "import watchdog" 2>/dev/null; then
    echo "Installing dependencies..."
    "$EDR_DIR/venv/bin/pip" install -r requirements.txt
fi

# Stop any existing collector
pkill -f "edr_collector_v2.py"
sleep 1

# Start collector with venv Python
echo "Starting EDR collector with venv Python..."
nohup "$VENV_PYTHON" "$COLLECTOR_SCRIPT" > collector.log 2>&1 &

echo "Collector started with PID: $!"
echo "Logs: $EDR_DIR/collector.log"
