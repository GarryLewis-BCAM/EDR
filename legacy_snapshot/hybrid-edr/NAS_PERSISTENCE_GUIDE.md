# NAS Persistence Guide
## Preventing NAS Unmounting Issues in EDR

**Created:** December 19, 2025  
**Status:** ✅ Implemented

---

## Problem Summary
The EDR system requires NAS shares (Apps, Data, Docker) to be mounted at `/Volumes/` for:
- Remote log storage at `/Volumes/Data/Logs/Security/edr`
- Database backups at `/Volumes/Apps/Services/EDR/backups`
- Configuration sync at `/Volumes/Apps/Services/EDR/configs`

When these shares unmount (due to network issues, Mac sleep, NAS reboot, etc.), the EDR continues running with local-only storage but loses its robust backup and remote logging capabilities.

---

## Multi-Layer Solution Implemented

### Layer 1: LaunchAgent Auto-Mount ✅
**What it does:** Automatically mounts NAS shares at login and every 5 minutes

**Files:**
- `/Users/garrylewis/Library/LaunchAgents/com.bcam.nas-automount.plist` - LaunchAgent definition
- `/Users/garrylewis/Security/hybrid-edr/auto_mount_nas.sh` - Mount script with retry logic

**Features:**
- Runs at login automatically
- Checks every 5 minutes (300 seconds) if shares are mounted
- Includes retry logic (3 attempts with 5-second delays)
- Checks NAS connectivity before attempting mount
- Logs all activity to `logs/nas_mount.log`
- Only runs when network is available (`NetworkState` trigger)

**To activate:**
```bash
launchctl load ~/Library/LaunchAgents/com.bcam.nas-automount.plist
```

**To check status:**
```bash
launchctl list | grep nas-automount
```

**To view logs:**
```bash
tail -f ~/Security/hybrid-edr/logs/nas_mount.log
```

### Layer 2: Health Check Integration ✅
**What it does:** Validates NAS health on demand

**File:** `/Users/garrylewis/Security/hybrid-edr/check_nas_health.sh`

**Features:**
- Checks NAS IP reachability (192.168.1.80)
- Verifies all 3 shares are mounted (Apps, Data, Docker)
- Tests write access to critical EDR paths
- Returns exit code 0 (success) or 1 (failure)

**Manual check:**
```bash
~/Security/hybrid-edr/check_nas_health.sh
```

**Example output:**
```
✅ NAS is reachable
✅ Apps is mounted
✅ Data is mounted
✅ Docker is mounted
✅ /Volumes/Data/Logs/Security/edr is accessible and writable
✅ /Volumes/Apps/Services/EDR/backups is accessible and writable

✅ NAS health check passed
```

### Layer 3: EDR Graceful Degradation ✅
**What it does:** EDR continues operating when NAS is unavailable

**Already implemented in:**
- `utils/logger.py` - Falls back to local logs
- `utils/db_v2.py` - Skips NAS backups gracefully
- `edr_collector_v2.py` - Logs warning but continues

**Behavior:**
- If NAS unavailable at startup: Warns but starts successfully
- Logs stored locally at: `/Users/garrylewis/Security/hybrid-edr/logs/`
- Database at: `/Users/garrylewis/Security/hybrid-edr/data/edr.db`
- When NAS becomes available: Auto-syncs logs every 5 minutes

### Layer 4: EDR Health Monitor ✅
**What it does:** EDR internally monitors NAS availability

**In:** `edr_collector_v2.py` (lines 476-484)

**Features:**
- Checks `/Volumes/Apps`, `/Volumes/Data`, `/Volumes/Docker` every 5 minutes
- Alerts via Telegram if < 2 of 3 shares mounted
- Integrated with health check cycle (every 5 minutes)

---

## Setup Instructions

### Initial Setup (One-Time)

1. **Save NAS credentials to Keychain:**
   ```bash
   # Mount manually first time to save password
   # Press Cmd+K in Finder
   # Connect to: smb://garrylewis@192.168.1.80/Data
   # Check "Remember this password in my keychain"
   # Repeat for Apps and Docker shares
   ```

2. **Load LaunchAgent:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.bcam.nas-automount.plist
   ```

3. **Verify it's loaded:**
   ```bash
   launchctl list | grep nas-automount
   # Should show: com.bcam.nas-automount
   ```

4. **Test immediately:**
   ```bash
   launchctl start com.bcam.nas-automount
   # Check logs
   tail -20 ~/Security/hybrid-edr/logs/nas_mount.log
   ```

### Verification

Run the health check:
```bash
~/Security/hybrid-edr/check_nas_health.sh
```

All checks should pass (✅). If any fail, investigate:
- Is NAS online? `ping 192.168.1.80`
- Can you access web UI? `http://192.168.1.80:5000`
- Are credentials saved? Check Keychain Access app

---

## Troubleshooting

### Shares Not Auto-Mounting

**Check LaunchAgent status:**
```bash
launchctl list | grep nas-automount
# If not listed:
launchctl load ~/Library/LaunchAgents/com.bcam.nas-automount.plist
```

**Check logs:**
```bash
tail -50 ~/Security/hybrid-edr/logs/nas_mount.log
tail -20 ~/Security/hybrid-edr/logs/nas_mount_error.log
```

**Common issues:**
- **Credentials not saved:** Mount manually via Finder (Cmd+K) and check "Remember password"
- **NAS offline:** Check `ping 192.168.1.80`
- **Network disconnected:** LaunchAgent waits for network before running

### Manual Mount

If auto-mount fails:
```bash
# Use the original script
~/Security/hybrid-edr/mount_nas.sh
```

### Disable Auto-Mount

If you need to disable:
```bash
launchctl unload ~/Library/LaunchAgents/com.bcam.nas-automount.plist
```

To re-enable:
```bash
launchctl load ~/Library/LaunchAgents/com.bcam.nas-automount.plist
```

---

## How It Prevents Future Issues

| Scenario | Solution | Layer |
|----------|----------|-------|
| Mac reboots | LaunchAgent auto-mounts at login | Layer 1 |
| Mac sleeps | LaunchAgent checks every 5 min | Layer 1 |
| NAS reboots | LaunchAgent retry logic | Layer 1 |
| Network glitch | Retry 3x with 5s delay | Layer 1 |
| Credentials expire | Saved in keychain | Setup |
| NAS permanently down | EDR continues locally | Layer 3 |
| Share unmounts silently | 5-min monitoring detects | Layer 1 + 4 |

---

## Monitoring

### Check LaunchAgent Activity
```bash
# View recent mounts
tail -100 ~/Security/hybrid-edr/logs/nas_mount.log

# Check if running now
ps aux | grep auto_mount_nas.sh | grep -v grep
```

### Check EDR Logs for NAS Issues
```bash
# Local logs
grep -i "nas\|mount" ~/Security/hybrid-edr/logs/edr_collector_v2.log | tail -20

# NAS logs (when available)
grep -i "nas\|mount" /Volumes/Data/Logs/Security/edr/edr_collector_v2.log | tail -20
```

### Check Current Mount Status
```bash
mount | grep "192.168.1.80"
# or
ls -la /Volumes/ | grep -E "Apps|Data|Docker"
```

---

## Best Practices

### Do's ✅
- Let LaunchAgent handle mounting automatically
- Check `nas_mount.log` periodically for patterns
- Keep NAS firmware updated
- Ensure stable network connection to NAS
- Test manual mount after Mac OS updates

### Don'ts ❌
- Don't manually unmount NAS shares (LaunchAgent will remount)
- Don't remove keychain credentials (breaks auto-mount)
- Don't disable LaunchAgent without reason
- Don't rely solely on Login Items (opens Finder windows)

---

## Files Reference

| File | Purpose |
|------|---------|
| `~/Library/LaunchAgents/com.bcam.nas-automount.plist` | Auto-mount configuration |
| `~/Security/hybrid-edr/auto_mount_nas.sh` | Mount script with retry |
| `~/Security/hybrid-edr/check_nas_health.sh` | Health validation |
| `~/Security/hybrid-edr/mount_nas.sh` | Manual mount (legacy) |
| `~/Security/hybrid-edr/logs/nas_mount.log` | Mount activity log |
| `~/Security/hybrid-edr/logs/nas_mount_error.log` | Error output |

---

## Testing

### Test Auto-Mount After Reboot
1. Run: `sudo reboot`
2. After login, wait 30 seconds
3. Check: `ls /Volumes/` should show Apps, Data, Docker
4. Verify: `~/Security/hybrid-edr/check_nas_health.sh`

### Test Recovery After Unmount
1. Manually unmount: `umount /Volumes/Data`
2. Wait 5 minutes (or less)
3. LaunchAgent should auto-remount
4. Check: `tail -20 ~/Security/hybrid-edr/logs/nas_mount.log`

### Test NAS Offline Scenario
1. Power off NAS or disconnect network
2. EDR should log warning but continue
3. Check: `tail -50 ~/Security/hybrid-edr/logs/edr_collector_v2.log`
4. Should see: "Using local logs only" (not crashing)

---

## Summary

You now have **4 layers of protection** against NAS mounting issues:

1. ✅ **Automatic mounting** at login and every 5 minutes
2. ✅ **Health monitoring** integrated into EDR
3. ✅ **Graceful degradation** when NAS unavailable
4. ✅ **Alerting** via Telegram when issues persist

**Key advantage:** EDR never stops working, even when NAS is down. When NAS comes back online, everything auto-recovers.

---

## Questions?

Run the health check:
```bash
~/Security/hybrid-edr/check_nas_health.sh
```

View LaunchAgent status:
```bash
launchctl list | grep nas-automount
tail -50 ~/Security/hybrid-edr/logs/nas_mount.log
```

Check EDR status:
```bash
ps aux | grep edr_collector_v2.py | grep -v grep
tail -30 ~/Security/hybrid-edr/logs/edr_collector_v2.log
```
