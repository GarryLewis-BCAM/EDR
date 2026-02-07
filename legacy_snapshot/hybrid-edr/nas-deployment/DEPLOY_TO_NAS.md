# Deploy EDR Dashboard to Synology NAS

## Prerequisites
- DS225+ with Docker/Container Manager installed
- Tailscale configured on NAS
- Mac's EDR database syncing to NAS

## Quick Deploy

### Step 1: Copy Files to NAS
```bash
# From your Mac
cd ~/Security/hybrid-edr
scp -r nas-deployment/* admin@192.168.1.80:/volume1/Docker/edr-dashboard/
```

### Step 2: Deploy Container
```bash
# SSH into NAS
ssh admin@192.168.1.80

# Navigate to deployment folder
cd /volume1/Docker/edr-dashboard

# Build and start
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

### Step 3: Access Dashboard

**Via Tailscale (from anywhere):**
```
http://[nas-tailscale-ip]:5000
```

**Via Local Network:**
```
http://192.168.1.80:5000
http://nas.local:5000
```

**Via Custom Domain (optional):**
Set up reverse proxy in DSM:
```
http://edr.yourdomain.com
```

## Automatic Database Sync

Your Mac's EDR collector already syncs to:
```
/volume1/Apps/Services/EDR/backups/edr.db
```

The dashboard reads from this backup (read-only), so it shows **live data** from your Mac!

## iPad Access

On your iPad (with Tailscale installed):

1. Open Safari
2. Navigate to: `http://[nas-tailscale-ip]:5000`
3. Add to Home Screen for app-like experience:
   - Tap Share button
   - Select "Add to Home Screen"
   - Name it "BCAM Security"
   - ✅ Now you have a dedicated icon!

**Tip:** The Tailscale IP stays the same, so the bookmark works from anywhere in the world.

## Maintenance

**View logs:**
```bash
docker-compose logs -f edr-dashboard
```

**Restart dashboard:**
```bash
docker-compose restart
```

**Update dashboard:**
```bash
# Copy new files from Mac
scp ~/Security/hybrid-edr/dashboard/app.py admin@192.168.1.80:/volume1/Docker/edr-dashboard/dashboard/

# Rebuild
docker-compose up -d --build
```

## Security Notes

- Dashboard runs as non-root user
- Database mounted read-only (can't modify data)
- Only accessible via Tailscale or local network
- No internet exposure required
- Automatic health checks every 30 seconds

## Troubleshooting

**Dashboard won't start:**
```bash
# Check Docker logs
docker-compose logs edr-dashboard

# Verify database exists
ls -lh /volume1/Apps/Services/EDR/backups/edr.db
```

**Can't access from iPad:**
```bash
# On NAS, check Tailscale IP
tailscale ip -4

# Test from Mac first
curl http://[nas-ip]:5000/api/health
```

**Database shows old data:**
```bash
# Check Mac's sync status
./status.sh

# Verify NAS backup timestamp
stat /Volumes/Apps/Services/EDR/backups/edr.db
```
