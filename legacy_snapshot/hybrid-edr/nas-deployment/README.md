# 🛡️ NAS EDR - 24/7 Protection for Your DS225+

## The Problem

Your NAS at **192.168.1.80** is:
- ❌ Directly exposed to the internet
- ❌ Hosting production app backends
- ❌ **Completely unprotected** when your Mac is off

**This is extremely dangerous!**

## The Solution

Deploy an **AI-powered EDR system** that runs 24/7 in Docker containers on your NAS:

✅ **Monitors** all NAS processes in real-time  
✅ **Detects** ransomware, cryptominers, brute force attacks  
✅ **AI Analysis** via local Ollama (no API costs)  
✅ **Auto-kills** threats automatically  
✅ **Blocks IPs** with Fail2ban  
✅ **Alerts you** via WhatsApp anywhere in the world  

---

## Quick Deploy (One Command)

### Prerequisites

1. **Enable SSH on NAS**: 
   - DSM → Control Panel → Terminal & SNMP → Enable SSH
   
2. **Install Docker on NAS**:
   - DSM → Package Center → Search "Container Manager" → Install

3. **Have your Twilio credentials** ready (already configured)

### Deploy

```bash
cd /Users/garrylewis/Security/hybrid-edr/nas-deployment
./deploy.sh
```

**That's it!** The script will:
1. Copy all EDR files to NAS
2. Deploy Docker containers
3. Download AI model (qwen2.5:7b)
4. Start 24/7 monitoring

Takes ~10 minutes (mostly AI model download).

---

## What Gets Deployed

| Service | Purpose | Memory |
|---------|---------|--------|
| **edr-collector** | Monitors NAS, kills threats | 512MB-2GB |
| **edr-ollama** | AI threat analysis (local) | 4-8GB |
| **edr-dashboard** | Web UI for monitoring | 512MB |
| **edr-fail2ban** | Auto-blocks brute force IPs | 128MB |

**Total RAM**: ~6-11GB (upgrade NAS to 8GB+ recommended)

---

## Access

### Dashboard
```
http://192.168.1.80:5050
```
- View threats in real-time
- See incident timeline
- Check collector status
- Review AI decisions

### Logs
```bash
ssh admin@192.168.1.80
cd /volume1/Docker/edr
docker logs -f edr-collector
```

### WhatsApp Alerts
You'll get alerts like:
> "🛡️ EDR Alert: I just blocked a cryptominer process (threat score: 92/100). The process was attempting to connect to a mining pool. Your NAS is safe."

---

## How It Works

```
1. Process starts on NAS
   ↓
2. EDR detects it
   ↓
3. AI analyzes (Ollama)
   - "Is this nginx legitimate or a disguised cryptominer?"
   - Threat score: 0-100
   ↓
4. AI decides action
   - Score >85: Auto-kill immediately
   - Score 70-85: AI decides (monitor vs kill)
   - Score 50-70: Monitor closely
   ↓
5. Execute & verify
   - Kill process with SIGKILL
   - Verify it's dead
   ↓
6. Alert you (WhatsApp)
   - AI writes natural language explanation
   ↓
7. Log everything
   - Full incident timeline in database
```

---

## Configuration

### Watch Your App Directories

Edit `config/config.yaml` on NAS:
```yaml
collection:
  file_monitor:
    paths:
      - "/volume1/Apps"           # Your backends
      - "/volume1/Development"
      - "/volume1/Docker"
```

### Whitelist Your Apps

Edit `config/response_policies.yaml`:
```yaml
whitelist:
  - nginx
  - postgres
  - redis
  - node
  - python3
  # Add your backend process names
```

---

## Testing

After deployment, test it:

```bash
# SSH to NAS
ssh admin@192.168.1.80

# Create suspicious process (EDR will detect and analyze)
nc -l 4444 &

# Watch logs
cd /volume1/Docker/edr
docker logs -f edr-collector

# Should see:
# AI evaluated nc: score=85, type=suspicious
# Threat handled autonomously: incident abc123
# WhatsApp alert sent
```

Check your WhatsApp - you should get an alert!

---

## Monitoring While Overseas

### Option 1: Direct Access (if NAS has public IP)
```
http://your-nas-ip:5050
```

### Option 2: Via VPN (Recommended)
1. Set up Tailscale on NAS
2. Connect from anywhere
3. Access `http://192.168.1.80:5050`

### Option 3: SSH Tunnel
```bash
ssh -L 5050:localhost:5050 admin@your-nas-ip
# Then open http://localhost:5050
```

### Option 4: WhatsApp Alerts
You don't need to check anything - the AI will alert you if threats are detected!

---

## Maintenance

### Update AI Model
```bash
ssh admin@192.168.1.80
docker exec edr-ollama ollama pull qwen2.5:7b
docker restart edr-collector
```

### View Incidents
```bash
docker exec edr-collector python -c "
from utils.db_v2 import EDRDatabase
db = EDRDatabase('/app/data/edr.db')
incidents = db.get_active_incidents()
for i in incidents:
    print(f'{i[\"process_name\"]}: {i[\"status\"]} (score: {i[\"threat_score\"]})')
"
```

### Backup Database
```bash
cp /volume1/Docker/edr/data/edr.db ~/Backups/edr-backup-$(date +%Y%m%d).db
```

---

## Uninstall

```bash
ssh admin@192.168.1.80
cd /volume1/Docker/edr
docker-compose down -v
rm -rf /volume1/Docker/edr
```

---

## Troubleshooting

### Collector not starting?
```bash
docker logs edr-collector
# Check for errors
```

### No AI analysis?
```bash
# Check if Ollama downloaded the model
docker exec edr-ollama ollama list
# Should show: qwen2.5:7b

# If not, download manually:
docker exec edr-ollama ollama pull qwen2.5:7b
```

### Not getting WhatsApp alerts?
Check `.env` file has correct Twilio credentials.

---

## Security Hardening (Do After Deployment)

### 1. DSM Firewall
Control Panel → Security → Firewall:
- ✅ Allow: 22 (SSH - your IP only)
- ✅ Allow: 80/443 (your apps)
- ✅ Allow: 5050 (dashboard - VPN only)
- ❌ Deny: Everything else

### 2. Fail2ban Active
Already configured to auto-block after 5 failed attempts on SSH/SMB.

### 3. Rate Limiting
Configure reverse proxy (Nginx) for your apps with rate limits.

---

## Cost

**Zero ongoing costs:**
- ✅ Ollama runs locally (no API fees)
- ✅ WhatsApp alerts via Twilio (free tier)
- ✅ All code open source

**One-time:**
- Maybe $50 to upgrade NAS RAM to 8GB (optional but recommended)

---

## Summary

**Before:** NAS exposed, unprotected when Mac off  
**After:** 24/7 AI-powered autonomous threat protection  

**Your backends stay safe even when you're overseas!** 🛡️

---

## Next Steps

1. Run `./deploy.sh`
2. Wait 10 mins for deployment
3. Access dashboard: `http://192.168.1.80:5050`
4. Test with `nc -l 4444` on NAS
5. Configure firewall rules in DSM
6. Go overseas with peace of mind!

Questions? Check `DEPLOY_TO_NAS.md` for detailed docs.
