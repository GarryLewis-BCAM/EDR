# Chrome & BCAMAPP.com SSL Fixes

## Problem 1: Chrome Blocking Port 5050 (Local Dashboard)

### Root Cause
Chrome on macOS requires certificates to be in the **System keychain**, not just the user keychain. Safari trusts user keychain certificates, but Chrome doesn't.

### Solution

#### Option A: Install CA System-Wide (Recommended)
```bash
cd ~/Security/hybrid-edr/ssl
./fix_chrome_trust.sh
```
This will prompt for your admin password and install the CA where Chrome can see it.

#### Option B: Manual Installation
1. Open **Keychain Access** app
2. Go to **File → Import Items**
3. Select `~/Security/hybrid-edr/ssl/bcam_root_ca.crt`
4. Choose **"System"** keychain (not "login")
5. Click **"Add"**
6. Find "BCAM EDR Root CA" in System keychain
7. Double-click it
8. Expand **"Trust"** section
9. Set **"When using this certificate"** to **"Always Trust"**
10. Close (will ask for password)
11. **Quit Chrome completely** (Cmd+Q)
12. Reopen Chrome
13. Visit `https://192.168.1.93:5050`

#### Option C: Temporary Bypass (Not Recommended)
On the Chrome warning page, type: `thisisunsafe` (no spaces, just type it - won't show on screen)

---

## Problem 2: BCAMAPP.com Redirect to BCAMAPP.ai

### Root Cause
When `BCAMAPP.com` redirects to `BCAMAPP.ai`, you need a valid SSL certificate on **BCAMAPP.com** for the redirect to work without warnings. The redirect happens AFTER the SSL handshake, so Chrome checks the certificate before following the redirect.

### Technical Explanation
```
User types: https://BCAMAPP.com
   ↓
1. Browser connects to BCAMAPP.com via HTTPS
2. Browser checks SSL certificate (FAILS if no cert or wrong cert)
   ↓ [ERROR SHOWN HERE]
3. Server would send 301/302 redirect to BCAMAPP.ai
   ↓ [Never reached due to SSL error]
4. Browser would load BCAMAPP.ai
```

### Solutions

#### Option 1: Get SSL Certificate for BCAMAPP.com (Best)
You need a valid SSL certificate for BCAMAPP.com, even if it just redirects.

**Free Options:**
1. **Let's Encrypt** (Free, 90-day renewal)
   - Use Certbot: `certbot certonly --webroot -d bcamapp.com -d www.bcamapp.com`
   - Auto-renews via cron
   
2. **Cloudflare** (Free SSL + Free Hosting)
   - Sign up at cloudflare.com
   - Add BCAMAPP.com as a site
   - Change nameservers to Cloudflare's
   - Enable "Always Use HTTPS"
   - Set up page rule: `bcamapp.com/*` → Forward to `https://bcamapp.ai/$1`
   - Cloudflare handles SSL automatically
   - **This is the easiest solution!**

3. **ZeroSSL** (Free alternative to Let's Encrypt)

#### Option 2: Multi-Domain Certificate
Get a single certificate that covers both:
- BCAMAPP.com
- BCAMAPP.ai

This allows one cert to secure both domains. Available from:
- Let's Encrypt (free): `certbot certonly -d bcamapp.com -d bcamapp.ai`
- Commercial CAs (paid)

#### Option 3: Use HTTP Redirect (Not Recommended)
If you can't get SSL for BCAMAPP.com:
- Make sure users go to `http://bcamapp.com` (not https)
- HTTP redirects don't require SSL
- But this is insecure and Google penalizes it

#### Option 4: Remove HSTS from BCAMAPP.com
If BCAMAPP.com previously had HSTS enabled, browsers remember it.

**Clear HSTS on your browser:**
1. Chrome: Visit `chrome://net-internals/#hsts`
2. Scroll to **"Delete domain security policies"**
3. Enter: `bcamapp.com`
4. Click **"Delete"**
5. Also delete `www.bcamapp.com` if needed

**Important:** This only fixes YOUR browser. Other users will still see errors.

#### Option 5: Check if BCAMAPP.com is HSTS Preloaded
If BCAMAPP.com was added to the HSTS preload list, ALL browsers will force HTTPS forever.

Check: https://hstspreload.org/
- Enter `bcamapp.com`
- If preloaded, you MUST have valid SSL
- Cannot be removed for 3-6 months even if you request

### Recommended Fix for BCAMAPP.com

**Use Cloudflare (5 minutes to fix):**

1. **Sign up at Cloudflare.com** (free)

2. **Add BCAMAPP.com**
   - Dashboard → Add Site
   - Enter: `bcamapp.com`
   - Choose Free plan

3. **Update Nameservers**
   - Cloudflare will show you 2 nameservers
   - Go to your domain registrar (GoDaddy, Namecheap, etc.)
   - Change nameservers to Cloudflare's
   - Wait 5-60 minutes for propagation

4. **Enable SSL**
   - Cloudflare → SSL/TLS → Overview
   - Set to **"Full"** or **"Flexible"**

5. **Create Page Rule**
   - Cloudflare → Rules → Page Rules
   - Create Rule:
     - URL: `*bcamapp.com/*`
     - Setting: **Forwarding URL** (301 - Permanent Redirect)
     - Destination: `https://bcamapp.ai/$1`
   - Save

6. **Test**
   - Wait 5 minutes
   - Visit `https://bcamapp.com`
   - Should redirect to `https://bcamapp.ai` without warnings!

### Alternative: If You Control the BCAMAPP.com Server

If you have hosting for BCAMAPP.com, install Let's Encrypt:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx  # or -apache

# Get certificate
sudo certbot certonly --nginx -d bcamapp.com -d www.bcamapp.com

# Certificates will be at:
# /etc/letsencrypt/live/bcamapp.com/fullchain.pem
# /etc/letsencrypt/live/bcamapp.com/privkey.pem

# Configure your redirect (Nginx example):
server {
    listen 443 ssl http2;
    server_name bcamapp.com www.bcamapp.com;
    
    ssl_certificate /etc/letsencrypt/live/bcamapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bcamapp.com/privkey.pem;
    
    return 301 https://bcamapp.ai$request_uri;
}
```

## Quick Reference

### Issue: Chrome blocks local dashboard (5050)
**Fix:** Run `~/Security/hybrid-edr/ssl/fix_chrome_trust.sh` and enter admin password

### Issue: BCAMAPP.com → BCAMAPP.ai shows SSL error
**Fix:** Use Cloudflare (free) or get Let's Encrypt cert for BCAMAPP.com

### Issue: Chrome shows "NET::ERR_CERT_AUTHORITY_INVALID"
**Fix:** Certificate not in System keychain or not trusted

### Issue: Chrome cached old SSL state
**Fix:** `chrome://net-internals/#hsts` → Delete domain

### Issue: HSTS preloaded domain
**Fix:** MUST have valid SSL, no way around it

## Verification

### Test Local Dashboard
1. Quit Chrome completely (Cmd+Q)
2. Reopen Chrome
3. Visit `https://192.168.1.93:5050`
4. Should show **green padlock**, no warnings
5. If still warning, run fix_chrome_trust.sh

### Test BCAMAPP.com
1. Clear browser cache
2. Visit `https://bcamapp.com`
3. Should redirect to `https://bcamapp.ai` smoothly
4. No SSL warnings at any point

## Need Help?

### Chrome still blocking 5050?
Check certificate installation:
```bash
security find-certificate -c "BCAM EDR Root CA" /Library/Keychains/System.keychain
```
Should return certificate info. If error, run fix_chrome_trust.sh again.

### BCAMAPP.com still showing errors?
1. Check which error you see
2. If "certificate invalid" → Need SSL cert on BCAMAPP.com
3. If "redirect loop" → Check server configuration
4. If "connection refused" → Check DNS/firewall

## Summary

- **Local Dashboard (5050):** Install CA in System keychain for Chrome
- **BCAMAPP.com redirect:** Get SSL certificate for source domain (use Cloudflare!)
- **HSTS issues:** Clear Chrome's HSTS cache or get proper SSL
- **Both fixed:** No more "Proceed to unsafe" clicking needed!

---

*The redirect issue is a common problem - you need SSL on BOTH the source and destination domains when using HTTPS. Cloudflare makes this free and automatic.*
