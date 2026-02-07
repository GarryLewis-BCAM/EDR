# NAS Quick Reference Card
**For BCAM EDR System**

---

## ✅ Check NAS Status (30 seconds)

```bash
# 1. Is everything healthy?
~/Security/hybrid-edr/check_nas_health.sh

# 2. Are shares mounted?
ls /Volumes/ | grep -E "Apps|Data|Docker"

# 3. Is LaunchAgent running?
launchctl list | grep nas-automount
```

---

## 🔧 Quick Fixes

### Shares Not Mounted
```bash
# Manual mount (immediate)
~/Security/hybrid-edr/mount_nas.sh

# Or trigger LaunchAgent
launchctl start com.bcam.nas-automount
```

### LaunchAgent Not Running
```bash
# Load it
launchctl load ~/Library/LaunchAgents/com.bcam.nas-automount.plist

# Verify
launchctl list | grep nas-automount
```

### NAS Can't Be Reached
```bash
# Check connectivity
ping 192.168.1.80

# Check NAS web UI
open http://192.168.1.80:5000
```

---

## 📊 View Logs

```bash
# Auto-mount activity
tail -50 ~/Security/hybrid-edr/logs/nas_mount.log

# EDR logs (local)
tail -50 ~/Security/hybrid-edr/logs/edr_collector_v2.log

# EDR logs (NAS - when available)
tail -50 /Volumes/Data/Logs/Security/edr/edr_collector_v2.log
```

---

## 🚨 Common Issues

| Symptom | Quick Fix |
|---------|-----------|
| "NAS storage unavailable" in EDR logs | Run `~/Security/hybrid-edr/mount_nas.sh` |
| Shares unmount after sleep | LaunchAgent will remount in < 5 min |
| LaunchAgent not working | Check Keychain has saved passwords |
| EDR not logging to NAS | Check shares mounted with `ls /Volumes/` |

---

## 🔄 After Mac Reboot

Wait 30 seconds after login, then verify:
```bash
~/Security/hybrid-edr/check_nas_health.sh
```

Should see all ✅ checks passing.

---

## 📞 Full Documentation

For complete details, see:
```bash
cat ~/Security/hybrid-edr/NAS_PERSISTENCE_GUIDE.md
```

---

## 🎯 One-Liner Status Check

```bash
echo "NAS Health:" && ~/Security/hybrid-edr/check_nas_health.sh && echo "" && echo "LaunchAgent:" && launchctl list | grep nas-automount && echo "" && echo "EDR Status:" && ps aux | grep edr_collector_v2.py | grep -v grep | awk '{print "✅ EDR running (PID: "$2")"}'
```
