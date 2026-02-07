#!/bin/bash
#
# Quick NAS mount script for BCAM EDR
# Manually mount NAS shares if login item fails
#

NAS_IP="192.168.1.80"
NAS_USER="garrylewis"
SHARES=("Apps" "Data" "Docker")
TIMEOUT=2

# Check if NAS is reachable first (prevents hanging)
if ! ping -c 1 -W $TIMEOUT "$NAS_IP" &>/dev/null; then
    echo "⚠️  NAS at $NAS_IP is not reachable - skipping mount"
    exit 0
fi

echo "🔗 Mounting BCAM NAS shares..."
echo ""

mounted=0
failed=0

for share in "${SHARES[@]}"; do
    if [ -d "/Volumes/$share" ]; then
        echo "✅ $share already mounted"
        ((mounted++))
    else
        echo "⏳ Mounting $share..."
        if osascript -e "mount volume \"smb://${NAS_USER}@${NAS_IP}/${share}\"" 2>/dev/null; then
            echo "✅ $share mounted successfully"
            ((mounted++))
        else
            echo "❌ $share mount failed"
            ((failed++))
        fi
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary: $mounted mounted, $failed failed"

if [ $failed -eq 0 ]; then
    echo "✅ All NAS shares mounted successfully!"
    exit 0
else
    echo "⚠️  Some shares failed to mount"
    echo "💡 Check NAS is online: ping $NAS_IP"
    exit 1
fi
