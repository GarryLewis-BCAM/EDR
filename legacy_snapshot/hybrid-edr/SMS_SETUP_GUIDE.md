# 5-Minute SMS Alert Setup (Twilio)

## Why SMS Instead of Email?

✅ **Instant delivery** - Get texts in 2-3 seconds  
✅ **Works overseas** - SMS works everywhere, even with bad data  
✅ **Hard to miss** - Phone buzzes in your pocket  
✅ **No spam folder** - Goes straight to messages  
✅ **100% open source** - Twilio has free tier!

---

## Step 1: Get Twilio Account (2 minutes)

### Free Tier Benefits:
- $15 credit (enough for ~500 alerts)
- No credit card needed initially
- Works internationally

### Sign Up:
1. Visit: https://www.twilio.com/try-twilio
2. Sign up with email
3. Verify your phone number
4. ✅ You get a free Twilio phone number!

---

## Step 2: Get Your Credentials (1 minute)

After signing up:

1. Go to: https://www.twilio.com/console
2. You'll see:
   - **Account SID** (looks like: `ACxxxxxxxxxxxxxxxxxxxx`)
   - **Auth Token** (click to reveal)
   - **My Twilio phone number** (looks like: `+15551234567`)

3. **Copy these!** You'll need them in the next step.

---

## Step 3: Configure EDR (2 minutes)

### Edit Config File:
```bash
cd ~/Security/hybrid-edr
nano config/config.yaml
```

### Find the `twilio_sms` section (around line 164):

**Before:**
```yaml
twilio_sms:
  enabled: false
  account_sid: ""
  auth_token: ""
  from_number: ""
  to_numbers:
    - ""
  min_severity: "high"
```

**After (with your details):**
```yaml
twilio_sms:
  enabled: true
  account_sid: "ACxxxxxxxxxxxxxxxxxxxx"  # From Twilio Console
  auth_token: "your_auth_token_here"     # From Twilio Console
  from_number: "+15551234567"            # Your Twilio number
  to_numbers:
    - "+15559876543"                     # YOUR phone number
  min_severity: "high"  # Only HIGH/CRITICAL alerts (avoids spam)
```

**Important:** 
- Phone numbers MUST include country code (e.g., `+1` for US)
- Keep quotes around all values
- You can add multiple phone numbers

### Save:
- Press `Ctrl + X`
- Press `Y`
- Press `Enter`

---

## Step 4: Test It! (30 seconds)

### Restart Collector:
```bash
cd ~/Security/hybrid-edr
source venv/bin/activate

# Stop if running
killall python3

# Start again
python3 edr_collector_v2.py
```

### Send Test Alert:
In another terminal:
```bash
cd ~/Security/hybrid-edr
source venv/bin/activate
python3 << 'EOF'
from utils.alerting import AlertingSystem, Alert, AlertPriority
import yaml

config = yaml.safe_load(open('config/config.yaml'))
alerter = AlertingSystem(config)

test_alert = Alert(
    title="EDR Test Alert",
    message="SMS is working! You'll get texts for critical threats.",
    priority=AlertPriority.HIGH,
    severity="high",
    source="TestSMS"
)

results = alerter.send_alert(test_alert)
print(f"SMS sent: {results}")
EOF
```

### Check Your Phone:
You should receive: **"🔴 BCAM EDR: EDR Test Alert..."**

---

## How It Works

### When You Get SMS:

**Example 1: Suspicious Process**
```
🔴 BCAM EDR: Suspicious Process Detected
Process: nc (netcat) scored 85/100
PID: 12345
```

**Example 2: Ransomware Blocked**
```
🚨 BCAM EDR: CRITICAL Threat Blocked
Ransomware detected encrypting files
Process killed, forensics captured
```

**Example 3: Unauthorized NAS Access**
```
🔴 BCAM EDR: NAS Access Attempt
50+ failed login attempts from 1.2.3.4
Auto-blocked, review logs
```

### Severity Levels:
- **info** (0-30): No SMS (logged only)
- **warning** (31-60): No SMS (logged only)
- **high** (61-85): ✅ **SMS Sent**
- **critical** (86-100): ✅ **SMS Sent**

This prevents spam - you only get texts for real threats!

---

## Cost Breakdown

**Twilio Pricing:**
- SMS: $0.0075 per message (less than 1 cent!)
- Free tier: $15 credit = ~2,000 messages
- International SMS: ~$0.04 per message

**Real-World Usage:**
- Normal month: 0-5 alerts = $0.04
- Busy month (false positives): 20 alerts = $0.15
- Attack scenario: 50 alerts = $0.38

**Compared to:**
- Email: Free but slower, spam folder issues
- Pushover: $5 one-time (good alternative!)
- PagerDuty: $19/month (overkill)

**Verdict:** SMS via Twilio is the sweet spot! 💰

---

## Troubleshooting

### "SMS not received"

**Check 1: Twilio Console**
```
Visit: https://www.twilio.com/console/sms/logs
See if message was sent successfully
```

**Check 2: Phone Number Format**
```yaml
# Wrong:
to_numbers:
  - "5559876543"        # Missing country code

# Right:
to_numbers:
  - "+15559876543"      # US number with +1
  - "+447700123456"     # UK number with +44
```

**Check 3: Verify Twilio Account**
Free trial accounts can only send to verified numbers.
Go to: https://www.twilio.com/console/phone-numbers/verified

### "Config incomplete" error

Make sure ALL fields are filled:
```yaml
twilio_sms:
  enabled: true
  account_sid: "ACxxxx..."   # Must start with AC
  auth_token: "your_token"    # 32 characters
  from_number: "+15551234567" # Your Twilio number
  to_numbers:                 # At least one number
    - "+15559876543"
  min_severity: "high"        # Must be: info/warning/high/critical
```

### "Free trial restrictions"

If you see this error, you need to:
1. Verify your phone number in Twilio Console
2. Or upgrade account (add $20 = 2,666 SMS!)

### Test SMS from Twilio Console

Visit: https://www.twilio.com/console/sms/getting-started/test-sms
Send a test SMS to verify your setup.

---

## Advanced: Multiple Numbers

Send alerts to your whole team:

```yaml
twilio_sms:
  enabled: true
  account_sid: "ACxxxx..."
  auth_token: "your_token"
  from_number: "+15551234567"
  to_numbers:
    - "+15559876543"  # Your phone
    - "+15559876544"  # Partner's phone
    - "+447700123456" # Colleague in UK
  min_severity: "critical"  # Only wake everyone for CRITICAL
```

---

## Alternative: Trello Integration

You mentioned having Trello! Here's how to get EDR alerts in Trello:

### Setup Trello Webhook:
1. Create a Trello board: "Security Alerts"
2. Get webhook URL:
   - Visit: https://trello.com/power-ups/admin
   - Create webhook for your board
3. Add to config:

```yaml
alerts:
  channels:
    webhook:
      enabled: true
      url: "https://api.trello.com/1/cards?key=...&token=..."
```

**Then:** Each alert creates a Trello card! Check them on iPad/phone via Trello app.

But honestly, **SMS is faster for critical threats**. Use Trello for audit trail!

---

## Summary

✅ **Setup time:** 5 minutes  
✅ **Cost:** ~$0.01 per alert  
✅ **Free tier:** $15 credit included  
✅ **Works overseas:** Yes  
✅ **Open source:** Yes  
✅ **iPad/iPhone:** Native Messages app  

**Next:** Deploy dashboard to NAS for 24/7 monitoring!

See: `DEPLOY_TO_NAS.md`
