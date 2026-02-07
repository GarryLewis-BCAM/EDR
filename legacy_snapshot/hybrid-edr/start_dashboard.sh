#!/bin/bash
# EDR Dashboard Startup Script
# This ensures the dashboard runs with the correct Python environment

EDR_DIR="/Users/garrylewis/Security/hybrid-edr"
VENV_PYTHON="$EDR_DIR/venv/bin/python3"
DASHBOARD_SCRIPT="$EDR_DIR/dashboard/app.py"

cd "$EDR_DIR"

# Check if venv Python exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment Python not found at $VENV_PYTHON"
    echo "Please run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Check if already running
if lsof -ti:5050 > /dev/null 2>&1; then
    echo "Dashboard is already running on port 5050"
    echo "Opening in browser..."
    open "http://localhost:5050"
    exit 0
fi

# Start dashboard with venv Python
echo "Starting BCAM Hybrid EDR Dashboard..."
echo "URL: http://localhost:5050"
echo "Press Ctrl+C to stop"
echo ""

"$VENV_PYTHON" "$DASHBOARD_SCRIPT"
