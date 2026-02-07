# EDR Dependency Management

## Problem: Watchdog Keeps Disappearing

### Root Cause
The EDR system has a virtual environment (`venv/`) but the collector was being launched with **system Python** instead of **venv Python**. This caused:
- Watchdog installed to system Python (via `pip3 install --break-system-packages`)
- System packages getting wiped or reset
- Repeated reinstallation of the same dependencies

### Solution

#### 1. Centralized Dependency Management
Created `requirements.txt` with all EDR dependencies:
```bash
# Core monitoring
psutil>=7.1.3
watchdog>=6.0.0

# Web framework
flask>=3.1.0
flask-cors>=6.0.1
flask-socketio>=5.4.1
python-socketio>=5.15.0

# Machine Learning
scikit-learn>=1.6.0
numpy>=2.3.4
pandas>=2.3.3
```

#### 2. Proper Launch Scripts
Created `start_collector.sh` that:
- Uses venv Python explicitly: `venv/bin/python3`
- Auto-installs dependencies if missing
- Prevents accidental system Python usage

#### 3. Environment Isolation
The venv at `/Users/garrylewis/Security/hybrid-edr/venv/` contains:
- Python 3.14 (via Homebrew)
- All EDR dependencies isolated from system
- Persistent across system updates

## Usage

### Installing Dependencies
```bash
cd /Users/garrylewis/Security/hybrid-edr
venv/bin/pip install -r requirements.txt
```

### Starting Services (Correct Way)
```bash
# Collector (uses venv automatically)
./start_collector.sh

# Dashboard (uses venv automatically)
./start_dashboard.sh
```

### Starting Services (Wrong Way - Don't Do This)
```bash
# ❌ WRONG - uses system Python
python3 edr_collector_v2.py

# ❌ WRONG - installs to system
pip3 install --break-system-packages watchdog
```

## Verification

Check which Python is being used:
```bash
# Check collector process
ps aux | grep edr_collector_v2.py
# Should show: /Users/garrylewis/Security/hybrid-edr/venv/bin/python3

# Check installed packages in venv
venv/bin/pip list | grep watchdog
# Should show: watchdog 6.0.0
```

## Recovery from Future Issues

If watchdog or other dependencies go missing:
```bash
# 1. Stop services
pkill -f edr_collector_v2.py
pkill -f dashboard/app.py

# 2. Reinstall all dependencies
venv/bin/pip install -r requirements.txt

# 3. Restart using launch scripts
./start_collector.sh
./start_dashboard.sh
```

## Why This Matters

**System Python** (`/opt/homebrew/bin/python3`):
- Shared across all projects
- Can be affected by system updates
- Package conflicts possible
- `--break-system-packages` is a red flag

**Venv Python** (`venv/bin/python3`):
- Isolated to this project only
- Survives system updates
- No package conflicts
- Proper dependency management

## Boot/Auto-Start Configuration

If you need the collector to start on boot, update any LaunchAgents or cron jobs to use:
```bash
/Users/garrylewis/Security/hybrid-edr/start_collector.sh
```

NOT:
```bash
python3 /Users/garrylewis/Security/hybrid-edr/edr_collector_v2.py
```
