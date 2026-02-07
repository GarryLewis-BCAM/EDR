# PREVENTION MEASURES IMPLEMENTED

## Problem: Collector Crashed Due to Python Cache

**Root Cause:** Python was running stale bytecode (.pyc files) from before 
we fixed the code. The source code was correct but Python cached the old 
compiled version.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Prevention Layer 1: AUTO-CLEAN ON STARTUP ✅

**File:** `edr_collector_v2.py` (lines 25-50)

**What it does:**
- Automatically clears ALL Python cache before starting
- Runs BEFORE importing any local modules
- Removes all __pycache__ directories
- Deletes all .pyc files
- Silent if no cache to clear

**Result:** Collector ALWAYS runs latest code, never stale bytecode

**Code Added:**
```python
def clear_python_cache():
    """Clear __pycache__ directories to prevent running stale bytecode"""
    project_root = Path(__file__).parent
    cleared_count = 0
    
    for pycache_dir in project_root.rglob('__pycache__'):
        try:
            shutil.rmtree(pycache_dir)
            cleared_count += 1
        except Exception:
            pass
    
    # Also remove .pyc files
    for pyc_file in project_root.rglob('*.pyc'):
        try:
            pyc_file.unlink()
        except Exception:
            pass
    
    if cleared_count > 0:
        print(f"✓ Cleared {cleared_count} Python cache directories")

# Clear cache before importing local modules
clear_python_cache()
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Prevention Layer 2: CLEAN RESTART SCRIPT ✅

**File:** `restart_collector_clean.sh`

**What it does:**
- Safe collector restart with built-in cache clearing
- Verifies critical files exist before starting
- Checks for errors in startup log
- Reports success/failure clearly

**Usage:**
```bash
cd ~/Security/hybrid-edr
./restart_collector_clean.sh
```

**5-Step Process:**
1. Stop existing collector gracefully
2. Clear Python bytecode cache
3. Verify all critical files present
4. Start collector fresh
5. Verify startup success + check for errors

**Benefits:**
- One command does everything safely
- Never forgets to clear cache
- Catches startup failures immediately
- Safe for automation/cron jobs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Prevention Layer 3: CRASH WATCHDOG ✅

**File:** `collector_watchdog.sh`

**What it does:**
- Monitors collector process every 30 seconds
- Auto-restarts if crashed
- Tracks crash reasons from logs
- Prevents infinite restart loops (max 5/hour)
- Sends critical alert if crash loop detected

**Usage (run in background):**
```bash
cd ~/Security/hybrid-edr
nohup ./collector_watchdog.sh &
```

**Or add to crontab:**
```bash
@reboot cd /Users/garrylewis/Security/hybrid-edr && ./collector_watchdog.sh &
```

**Safety Features:**
- Max 5 restarts per hour (prevents crash loops)
- Logs all crashes with reasons to watchdog.log
- Uses clean restart script (clears cache)
- Exits if unable to restart (manual intervention needed)
- Creates alert file at /tmp/edr_critical_alert.txt

**Watchdog Log Location:**
`~/Security/hybrid-edr/watchdog.log`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Prevention Layer 4: LOCALHOST SAFELIST ✅

**File:** `collectors/network_tracker.py` (lines 38-43)

**What it does:**
- IPv6 localhost (::1) added to safe_networks
- IPv4-mapped IPv6 localhost (::ffff:127.) added
- Prevents false positives on local database connections

**Result:** 
- Postgres ::1:5432 no longer flagged as threat
- All localhost traffic filtered out
- No more confusing MEDIUM threats on system services

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## How These Work Together

### Scenario 1: Code Update
1. You edit collectors/file_monitor.py
2. Run `./restart_collector_clean.sh`
3. Script clears cache automatically
4. Collector starts with NEW code (not cached)
5. No crashes from stale bytecode

### Scenario 2: Unexpected Crash
1. Collector crashes for ANY reason
2. Watchdog detects within 30 seconds
3. Watchdog logs crash reason
4. Watchdog runs clean restart script
5. Cache cleared automatically
6. Collector back online in < 1 minute

### Scenario 3: Crash Loop (Bad Code)
1. Collector crashes
2. Watchdog restarts it
3. Crashes again (bad code)
4. Watchdog restarts again
5. After 5 crashes in 1 hour...
6. Watchdog gives up (prevents infinite loop)
7. Critical alert created
8. You get notified to fix code manually

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Testing Prevention Measures

### Test 1: Cache Clearing Works
```bash
# Create fake cache
mkdir -p ~/Security/hybrid-edr/test/__pycache__
touch ~/Security/hybrid-edr/test/__pycache__/test.pyc

# Restart collector
./restart_collector_clean.sh

# Verify cache cleared
ls ~/Security/hybrid-edr/test/__pycache__  # Should be gone
```

### Test 2: Watchdog Auto-Restart
```bash
# Start watchdog
nohup ./collector_watchdog.sh &

# Kill collector manually
pkill -f edr_collector

# Wait 30 seconds
sleep 30

# Check if restarted
ps aux | grep edr_collector  # Should be running
cat watchdog.log  # Should show restart
```

### Test 3: Localhost Filtering
```bash
# Check network events
sqlite3 data/edr.db "SELECT COUNT(*) FROM network_events WHERE dest_ip='::1';"
# Should be 0 (filtered out)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created/Modified

### Created:
✅ `restart_collector_clean.sh` - Safe restart with cache clearing
✅ `collector_watchdog.sh` - Auto-restart on crash
✅ `PREVENTION_MEASURES.md` - This document

### Modified:
✅ `edr_collector_v2.py` - Auto-clears cache on startup
✅ `collectors/network_tracker.py` - Added ::1 to safe_networks

### Log Files:
📝 `watchdog.log` - Watchdog activity log
📝 `collector_startup.log` - Latest startup log
📝 `collector.log` - Main collector log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Recommended Setup

### Option A: Manual Monitoring
- Use `./restart_collector_clean.sh` when making changes
- Manually monitor collector.log

### Option B: Automatic Monitoring (RECOMMENDED)
1. Start watchdog on boot:
```bash
# Add to crontab
crontab -e

# Add line:
@reboot cd /Users/garrylewis/Security/hybrid-edr && nohup ./collector_watchdog.sh &
```

2. Collector auto-restarts on crash
3. You get alerted if crash loop detected
4. Cache always cleared on restart

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Summary

**4 layers of protection prevent this from happening again:**

1. ✅ **Auto-clean on startup** - Collector clears its own cache
2. ✅ **Clean restart script** - Manual restarts always clear cache
3. ✅ **Crash watchdog** - Auto-restarts with cache clearing
4. ✅ **Localhost safelist** - Prevents false positives

**You can't get stale bytecode anymore because:**
- Every collector start clears cache first
- Every restart script clears cache
- Watchdog clears cache on auto-restart
- 3 independent layers doing the same thing

**This is robust because:**
- No single point of failure
- Works even if one layer fails
- Prevents crash loops
- Alerts you if something is seriously wrong
- Self-healing within 30 seconds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**The collector won't crash from cache issues again.**
