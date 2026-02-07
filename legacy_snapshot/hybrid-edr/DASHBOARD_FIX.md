# Dashboard Issues Fixed

## Problems Encountered

1. **Desktop shortcut not working** - Was checking HTTP port 5050, but dashboard runs on HTTPS
2. **Dashboard frozen** - Multiple dashboard processes running, port conflicts
3. **LaunchAgent using wrong Python** - Was using system Python via `source venv/bin/activate`

## Solutions Implemented

### 1. Fixed Desktop Launcher
**Updated:** `/Users/garrylewis/Desktop/EDR Dashboard.app`

- Changed from `http://localhost:5050` → `https://localhost:5050`
- Added `-k` flag to curl for self-signed SSL cert
- Now properly detects running dashboard

**To test:**
```bash
open "/Users/garrylewis/Desktop/EDR Dashboard.app"
```

### 2. Fixed LaunchAgent
**Updated:** `start_dashboard_daemon.sh`

**Before:**
```bash
source venv/bin/activate
python3 dashboard/app.py
```

**After:**
```bash
VENV_PYTHON="/Users/garrylewis/Security/hybrid-edr/venv/bin/python3"
exec "$VENV_PYTHON" dashboard/app.py
```

**Benefits:**
- Uses venv Python explicitly (no environment activation needed)
- Consistent with collector fix
- Survives PATH changes

### 3. Updated Interactive Start Script
**Updated:** `start_dashboard.sh`

- Uses venv Python explicitly
- Checks if port 5050 is already in use
- Opens browser if dashboard already running
- Proper error handling

## Dashboard URLs

The dashboard runs on **HTTPS** with a self-signed certificate:

- **Local:** https://localhost:5050
- **Network:** https://192.168.1.93:5050
- **Tailscale:** https://100.70.131.10:5050

**Note:** You'll see a browser warning about the self-signed certificate - click "Advanced" → "Proceed" to access.

## How Dashboard Starts

### Automatic (Boot/LaunchAgent):
```
macOS Boot
  ↓
~/Library/LaunchAgents/com.bcam.edr.dashboard.plist
  ↓
start_dashboard_daemon.sh
  ↓
venv/bin/python3 dashboard/app.py
  ↓
Dashboard on https://0.0.0.0:5050
```

### Manual (Desktop Icon):
```
Click EDR Dashboard.app
  ↓
Check https://localhost:5050
  ↓
If running → Open browser
If not → Show error
```

### Manual (Command Line):
```bash
cd ~/Security/hybrid-edr
./start_dashboard.sh
```

## Verification

### Check Dashboard Status:
```bash
# Check if running
launchctl list | grep edr.dashboard

# Check logs
tail -f /tmp/edr_dashboard_launchd_error.log

# Test API
curl -sk https://localhost:5050/api/health
```

### Check Port Usage:
```bash
lsof -ti:5050
# Should show one Python process

ps -p $(lsof -ti:5050) -o command
# Should show: /path/to/venv/bin/python3 dashboard/app.py
```

## Troubleshooting

### "Dashboard is not responding"
```bash
# Check LaunchAgent logs
tail -50 /tmp/edr_dashboard_launchd_error.log

# Restart LaunchAgent
launchctl stop com.bcam.edr.dashboard
launchctl start com.bcam.edr.dashboard
```

### "Port 5050 already in use"
```bash
# Find process using port
lsof -ti:5050

# Kill it
lsof -ti:5050 | xargs kill -9

# Restart dashboard
launchctl start com.bcam.edr.dashboard
```

### Desktop Launcher Does Nothing
```bash
# Test curl manually
curl -sk -o /dev/null -w '%{http_code}' https://localhost:5050
# Should return: 200

# If returns 000, dashboard is not running
launchctl list | grep edr.dashboard
```

## What Changed vs Before

| Aspect | Before | After |
|--------|--------|-------|
| **Desktop Launcher URL** | http://localhost:5050 | https://localhost:5050 |
| **LaunchAgent Python** | `source venv; python3` | `venv/bin/python3` (explicit) |
| **Start Script** | Used system python3 | Uses venv/bin/python3 |
| **SSL** | HTTP only | HTTPS with self-signed cert |
| **Consistency** | Mixed Python usage | All use venv explicitly |

## Benefits

1. **Desktop launcher works** - Correctly detects HTTPS dashboard
2. **No more freezes** - Proper process management
3. **Consistent environment** - All scripts use venv Python
4. **Auto-recovery** - LaunchAgent restarts dashboard if it crashes
5. **Better logging** - All logs in /tmp/ for troubleshooting

## Related Files

- Desktop launcher: `~/Desktop/EDR Dashboard.app`
- LaunchAgent config: `~/Library/LaunchAgents/com.bcam.edr.dashboard.plist`
- Daemon script: `start_dashboard_daemon.sh`
- Interactive script: `start_dashboard.sh`
- Logs: `/tmp/edr_dashboard_launchd*.log`
