# NAS Protection Strategy

## Can It Protect NAS Data? YES! ✅

Your EDR system can protect your NAS in **three layers:**

---

## Layer 1: File Integrity Monitoring (Immediate - No Setup)

### What It Does:
Watches NAS files for suspicious changes from your Mac's perspective.

### How It Works:
Your Mac's EDR collector **already monitors** these mounted NAS folders:
```
/Volumes/Apps/Services/EDR/
/Volumes/Data/
/Volumes/Development/BCAM_Projects/
```

**It detects:**
- ❌ Mass file deletions (ransomware!)
- ❌ Unauthorized file modifications
- ❌ Suspicious file creation patterns
- ❌ Files with unusual extensions (.encrypted, .locked)
- ✅ Your normal daily file operations

**Real Example:**
If ransomware on your Mac tries to encrypt NAS files, the EDR sees:
1. Rapid file modifications (100+ files/second)
2. File extension changes (.docx → .encrypted)
3. Suspicious process behavior
4. **ALERT: Critical threat detected!**
5. **ACTION: Kill process, disconnect network, notify you**

**Status:** ✅ Already working! Check your config at:
```bash
grep -A 5 "monitored_directories:" ~/Security/hybrid-edr/config/config.yaml
```

---

## Layer 2: NAS-Side Monitoring (Future - Wazuh Deployment)

### What It Adds:
Monitors NAS **from inside the NAS itself** - catches threats your Mac can't see.

### Deploy Wazuh on NAS:

**Step 1: Deploy Wazuh Server**
```bash
# SSH into your NAS
ssh admin@192.168.1.80

# Create Wazuh directory
mkdir -p /volume1/Docker/wazuh
cd /volume1/Docker/wazuh

# Copy Wazuh config from Mac
# (Use the wazuh-docker-compose.yml I created)

# Start Wazuh
docker-compose up -d

# Access Wazuh Dashboard
# https://192.168.1.80:5601
```

**Step 2: Configure NAS Monitoring**
Wazuh will watch:
- ✅ DSM login attempts (failed/successful)
- ✅ File integrity on critical NAS folders
- ✅ Docker container behavior
- ✅ Network traffic to/from NAS
- ✅ System resource abuse
- ✅ Malware signatures
- ✅ Configuration changes

**Step 3: Connect Your Mac**
```bash
# Install Wazuh agent on Mac
brew install wazuh-agent

# Configure to report to NAS
sudo /Library/Ossec/bin/agent-auth -m 192.168.1.80
sudo /Library/Ossec/bin/ossec-control start
```

Now your Mac **and** NAS are both monitored centrally!

---

## Layer 3: Network-Level Protection (Advanced)

### What It Adds:
Monitors **all network traffic** between devices and the NAS.

### Deploy Suricata IDS:
```bash
# On NAS
docker run -d \
  --name suricata \
  --network host \
  -v /volume1/Data/Logs/Security/suricata:/var/log/suricata \
  jasonish/suricata:latest \
  -i eth0
```

**It detects:**
- Port scans targeting NAS
- Brute-force login attempts
- Exploit attempts (CVE-based)
- Suspicious SMB/NFS traffic
- Data exfiltration patterns

---

## Protection Summary

| Threat Type | Layer 1 (Mac EDR) | Layer 2 (Wazuh) | Layer 3 (IDS) |
|-------------|-------------------|-----------------|---------------|
| Ransomware on Mac encrypting NAS files | ✅ Detects & blocks | ✅ Forensics | ✅ Logs traffic |
| Malware on NAS itself | ❌ | ✅ Detects | ✅ Detects |
| Unauthorized NAS login | ⚠️ Indirect | ✅ Detects | ✅ Detects |
| Mass file deletion | ✅ Detects | ✅ Detects | ⚠️ Indirect |
| Network attacks on NAS | ❌ | ⚠️ Partial | ✅ Detects |
| Insider threat (authorized user) | ✅ Behavioral anomalies | ✅ Audit trail | ✅ Traffic analysis |

---

## Specific NAS Threats & Defenses

### Threat 1: Ransomware
**Scenario:** Your Mac gets infected, starts encrypting NAS files.

**Defense (Already Active!):**
1. Mac EDR sees rapid file changes
2. Scores threat as 95/100
3. Sends immediate macOS notification
4. Kills malicious process
5. Logs forensic data to NAS
6. You get alert on iPad (if overseas)

**Additional Protection (Future):**
- Wazuh creates immutable backup snapshots
- IDS blocks network traffic from infected Mac

### Threat 2: Unauthorized Access
**Scenario:** Hacker brute-forces your NAS password.

**Defense (Layer 2 - Wazuh):**
1. DSM logs 50+ failed login attempts
2. Wazuh detects pattern
3. Alerts you + auto-blocks IP
4. Preserves forensic evidence

### Threat 3: Data Exfiltration
**Scenario:** Malware slowly copies files off NAS.

**Defense (Layer 3 - IDS):**
1. Suricata sees unusual outbound traffic
2. Detects large data transfers to unknown IP
3. Alerts you
4. Provides packet captures for investigation

### Threat 4: Docker Container Compromise
**Scenario:** Attacker exploits vulnerable NAS Docker container.

**Defense (Layer 2 - Wazuh):**
1. Monitors container behavior
2. Detects privilege escalation attempts
3. Alerts on unexpected processes
4. Can auto-stop container

---

## Quick Setup (Priority Order)

### Today (Already Done!)
✅ Mac EDR monitors NAS-mounted folders
✅ File integrity monitoring active
✅ Behavioral analysis running

### This Week (Recommended)
1. Deploy EDR dashboard to NAS (see DEPLOY_TO_NAS.md)
2. Test iPad access via Tailscale
3. Configure email alerts for critical threats

### Next Month (Full Protection)
1. Deploy Wazuh on NAS (wazuh-docker-compose.yml)
2. Install Wazuh agent on Mac
3. Configure NAS file integrity rules
4. Deploy Suricata IDS

---

## Real-World Example

**Scenario:** You're overseas, ransomware hits your Mac at 2 AM.

**What Happens:**

**2:00:15 AM** - Ransomware starts encrypting documents  
**2:00:17 AM** - Mac EDR detects 200 file modifications in 2 seconds  
**2:00:18 AM** - Threat scored 95/100, process killed immediately  
**2:00:19 AM** - macOS notification sent (Mac wakes you if nearby)  
**2:00:20 AM** - Alert logged to NAS (persistent record)  
**2:00:21 AM** - Email sent to your phone: "⚠️ CRITICAL: Ransomware blocked"  

**6:00 AM** - You wake up in hotel, check email  
**6:05 AM** - Open iPad, connect to Tailscale  
**6:06 AM** - Visit EDR dashboard (on NAS)  
**6:07 AM** - See incident timeline, verify files safe  
**6:08 AM** - Review forensic data, confirm threat eliminated  
**6:10 AM** - Back to sleep, NAS data protected ✅

---

## Cost Breakdown

| Component | Cost | Purpose |
|-----------|------|---------|
| Mac EDR (Current) | **$0** | Protects Mac + monitors NAS mounts |
| NAS Dashboard | **$0** | Remote monitoring via Tailscale |
| Wazuh (NAS) | **$0** | NAS-side intrusion detection |
| Suricata IDS | **$0** | Network traffic analysis |
| **TOTAL** | **$0** | Enterprise-grade protection |

---

## Notifications When Overseas

### Setup Email Alerts:

Edit `config/config.yaml`:
```yaml
alerting:
  channels:
    email:
      enabled: true
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      from_address: "edr@yourdomain.com"
      to_addresses:
        - "your-email@gmail.com"
      username: "your-email@gmail.com"
      password: "app-specific-password"
      min_severity: "warning"  # Get emails for warning+
```

Restart collector:
```bash
killall python3
python3 edr_collector_v2.py
```

Now you get:
- ✅ Email on critical threats (immediately)
- ✅ Daily summary email (8 AM)
- ✅ Weekly security report (Mondays)

### iPad Push Notifications (Advanced):

Use **Pushover** service ($5 one-time fee):
```yaml
alerting:
  channels:
    pushover:
      enabled: true
      user_key: "your-pushover-key"
      api_token: "your-app-token"
      min_severity: "high"  # Only critical alerts
```

Now your iPad/iPhone get **instant push notifications** for threats, anywhere in the world!

---

## Next Steps

1. ✅ **Test current protection:** Create a test file on NAS, rapidly modify it, watch for alert
2. ⬜ **Deploy dashboard to NAS:** Follow DEPLOY_TO_NAS.md
3. ⬜ **Setup email alerts:** Edit config, restart collector
4. ⬜ **Future: Deploy Wazuh** for NAS-side monitoring

**Questions?** Check the troubleshooting section in README.md or review logs:
```bash
tail -f ~/Security/hybrid-edr/logs/edr_collector_v2.log
```
