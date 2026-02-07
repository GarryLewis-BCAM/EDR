#!/bin/bash
# EDR Dashboard Auto-start Script (for LaunchAgent)

EDR_DIR="/Users/garrylewis/Security/hybrid-edr"
VENV_PYTHON="$EDR_DIR/venv/bin/python3"

cd "$EDR_DIR"

# Increase file descriptor limit to avoid "too many open files" errors
ulimit -n 10240

# Start dashboard with venv Python (runs in foreground for LaunchAgent)
exec "$VENV_PYTHON" dashboard/app.py
