# iPad Dashboard Fix - HTTPS Update

## Problem
iPad shortcut stopped working because the dashboard now uses **HTTPS** instead of HTTP.

**Old URL (broken):** `http://100.70.131.10:5050`  
**New URL (working):** `https://100.70.131.10:5050`

## Solution

### Update Your iPad Shortcut

1. **Open Shortcuts app on iPad**

2. **Find your EDR Dashboard shortcut**

3. **Tap the shortcut to edit (three dots ⋯)**

4. **Update the URL in the "Open URLs" action:**
   - Change: `Brave://open-url?url=http://100.70.131.10:5050`
   - To: `Brave://open-url?url=https://100.70.131.10:5050`
   
   Just add the **s** after `http`

5. **Save the shortcut**

6. **Test it** - Tap the shortcut from your home screen

## Expected Behavior

When you tap the shortcut:
1. Brave browser opens
2. You'll see a **certificate warning** (this is normal - self-signed cert)
3. Tap **"Advanced"**
4. Tap **"Proceed to 100.70.131.10 (unsafe)"**
5. Dashboard loads! 🎉

**Note:** You only need to bypass the certificate warning once per browser session. After that, the shortcut works smoothly.

## Alternative: Create New Shortcut

If editing is difficult, create a new one:

### Steps:
1. Open **Shortcuts app**
2. Tap **"+"** to create new shortcut
3. Search for **"Open URLs"** action
4. In the URL field, enter:
   ```
   Brave://open-url?url=https://100.70.131.10:5050
   ```
5. Tap **"⋯"** (three dots) at top right
6. Enable **"Add to Home Screen"**
7. Name it: **"EDR Dashboard"**
8. Tap **"Add"**
9. Done! Icon appears on home screen

## Why This Happened

The dashboard was upgraded to use HTTPS for security:
- ✅ Encrypted connection
- ✅ Secure API access
- ✅ Protection against network sniffing

The self-signed certificate warning is expected because we're not using a certificate authority (CA). For internal/personal use, this is perfectly fine.

## Verification

Test the URL works from your iPad:

**Safari or Brave:**
1. Open browser
2. Go to: `https://100.70.131.10:5050`
3. Accept certificate warning
4. Dashboard should load

If it doesn't load, check:
- Tailscale is connected on iPad
- Mac's Tailscale IP hasn't changed (run `tailscale ip -4` on Mac)
- Dashboard is running on Mac (check desktop launcher)

## Tailscale IP Reference

**Mac (iMac):** 100.70.131.10  
**iPad:** 100.104.153.101

If Mac's IP changes, you'll need to update the shortcut with the new IP.

## Quick Test from Mac

To verify HTTPS works via Tailscale:
```bash
curl -sk https://100.70.131.10:5050/api/health
# Should return JSON with "status": "healthy"
```

## Troubleshooting

### "Cannot connect to server"
- Check Tailscale is connected on iPad
- Verify Mac dashboard is running: `launchctl list | grep edr.dashboard`
- Test from Mac: `curl -sk https://100.70.131.10:5050`

### Certificate warning every time
- This is normal for self-signed certs
- Just tap "Advanced" → "Proceed" each time
- Alternative: Use HTTP on local network only (not recommended)

### Shortcut does nothing
- Make sure URL has `Brave://` prefix (capital B)
- Verify format: `Brave://open-url?url=https://100.70.131.10:5050`
- Try creating new shortcut instead of editing

## Summary

**Quick Fix:**  
Change `http://` to `https://` in your iPad shortcut URL.

**Full URL:**  
`Brave://open-url?url=https://100.70.131.10:5050`

That's it! Your iPad dashboard access is now restored. 🎉
