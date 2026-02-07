#!/bin/bash
# Quick Telegram Bot Setup for BCAM EDR

echo "============================================================"
echo "   Telegram Bot Setup for BCAM EDR"
echo "   Free, Global, Instant Alerts"
echo "============================================================"
echo ""
echo "📱 STEP 1: Create Your Bot (2 minutes)"
echo "   1. Open Telegram on your phone/computer"
echo "   2. Search for: @BotFather"
echo "   3. Start chat and send: /newbot"
echo "   4. Choose a name (e.g., 'BCAM EDR Alerts')"
echo "   5. Choose a username (e.g., 'bcam_edr_bot')"
echo "   6. Copy the bot token (123456:ABC-DEF...)"
echo ""
echo "💬 STEP 2: Get Your Chat ID (1 minute)"
echo "   1. Search for: @userinfobot"
echo "   2. Start chat and send any message"
echo "   3. It will reply with your chat ID (e.g., 123456789)"
echo ""
echo "⚙️  STEP 3: Configure EDR"
echo ""
read -p "Enter your bot token: " BOT_TOKEN
read -p "Enter your chat ID: " CHAT_ID

if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Both token and chat ID are required"
    exit 1
fi

# Update config
CONFIG_FILE="config/config.yaml"

echo ""
echo "Updating $CONFIG_FILE..."

# Use sed to enable Telegram and add credentials
sed -i.bak "s/enabled: false  # Set to true after setup/enabled: true/" "$CONFIG_FILE"
sed -i.bak "s/bot_token: \"\"/bot_token: \"$BOT_TOKEN\"/" "$CONFIG_FILE"
sed -i.bak "s/- \"\"/- \"$CHAT_ID\"/" "$CONFIG_FILE"

echo "✅ Configuration updated!"
echo ""
echo "🧪 Testing Telegram alerts..."

# Test alert
python3 << EOF
import sys
sys.path.insert(0, '.')
from utils.config_validator import validate_config_file
from utils.alerting import AlertingSystem, Alert, AlertPriority

config = validate_config_file('config/config.yaml')
alerter = AlertingSystem(config)

alert = Alert(
    title="✅ BCAM EDR Setup Complete",
    message="Telegram alerts are working!\n\nYou'll receive:\n• UPS disconnect alerts\n• Critical threats\n• System health warnings",
    priority=AlertPriority.MEDIUM,
    severity="medium",
    source="Setup"
)

results = alerter.send_alert(alert)
print(f"\nAlert sent: {results}")
EOF

echo ""
echo "============================================================"
echo "   ✅ Setup Complete!"
echo ""
echo "   Check your Telegram for the test message"
echo "   Restart EDR to activate: ./restart_edr.sh"
echo "============================================================"
