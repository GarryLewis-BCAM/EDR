# BCAM NAS Auto-Mount Setup

## Overview
Automatically mounts NAS shares on boot for EDR backups, logs, and configuration storage.

## Configuration

**NAS Details:**
- IP: `192.168.1.80`
- Username: `garrylewis`
- Shares: `Apps`, `Data`, `Docker`

**EDR Paths:**
- Backups: `/Volumes/Apps/Services/EDR/backups`
- Logs: `/Volumes/Data/Logs/Security/edr`
- Config: `/Volumes/Apps/Services/EDR/configs`
- Wazuh Data: `/Volumes/Docker/wazuh`

## Auto-Mount on Boot

### Login Item (Automatic)
A macOS login item runs on boot to mount all NAS shares:

**Location:** `/Users/garrylewis/Library/Scripts/mount_bcam_nas_v2.app`

**How it works:**
1. Runs automatically when you log in
2. Checks if shares are already mounted
3. Mounts each share using stored Keychain credentials
4. Reports success/failure

**View login items:**
```bash
osascript -e 'tell application "System Events" to get the name of every login item'
```

### Manual Mount

If auto-mount fails, use the convenience script:

```bash
cd /Users/garrylewis/Security/hybrid-edr
./mount_nas.sh
```

Or mount individually:
```bash
osascript -e 'mount volume "smb://garrylewis@192.168.1.80/Apps"'
osascript -e 'mount volume "smb://garrylewis@192.168.1.80/Data"'
osascript -e 'mount volume "smb://garrylewis@192.168.1.80/Docker"'
```

## Verify Mount Status

Check if shares are mounted:
```bash
ls -la /Volumes/ | grep -E 'Apps|Data|Docker'
```

Check dashboard health:
```bash
curl -s http://localhost:5050/api/health | grep nas_available
```

## Troubleshooting

### Shares won't mount
1. **Check NAS is online:**
   ```bash
   ping 192.168.1.80
   ```

2. **Verify credentials in Keychain:**
   - Open Keychain Access app
   - Search for "192.168.1.80"
   - Ensure password is stored for user `garrylewis`

3. **Re-run mount script:**
   ```bash
   ./mount_nas.sh
   ```

4. **Check script logs:**
   ```bash
   osascript /Users/garrylewis/Library/Scripts/mount_bcam_nas_v2.scpt
   ```

### Update username or IP

Edit the AppleScript:
```bash
open -e /Users/garrylewis/Library/Scripts/mount_bcam_nas_v2.scpt
```

Change these lines:
```applescript
set nasIP to "192.168.1.80"
set nasUser to "garrylewis"
```

Then recompile:
```bash
osacompile -o ~/Library/Scripts/mount_bcam_nas_v2.app ~/Library/Scripts/mount_bcam_nas_v2.scpt
```

## Security Notes

- Passwords are stored securely in macOS Keychain
- SMB connections use encrypted credentials
- Mount script does NOT store passwords in plain text
- First mount may prompt for password (then stored in Keychain)

## Files

| File | Purpose |
|------|---------|
| `~/Library/Scripts/mount_bcam_nas_v2.scpt` | AppleScript source |
| `~/Library/Scripts/mount_bcam_nas_v2.app` | Compiled login item |
| `/Users/garrylewis/Security/hybrid-edr/mount_nas.sh` | Manual mount helper |
| `/Users/garrylewis/Security/hybrid-edr/config/config.yaml` | EDR NAS paths config |

---

**Last Updated:** 2025-12-03  
**Status:** ✅ Operational  
**Login Item:** `mount_bcam_nas_v2`
