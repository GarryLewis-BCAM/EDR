#!/bin/bash
# Fix macOS Application Firewall to allow NAS access

echo "=========================================="
echo "macOS Firewall Fix for NAS Access"
echo "=========================================="
echo ""
echo "This will temporarily allow terminal tools to reach your NAS."
echo "You'll need to enter your password."
echo ""

# Check current firewall state
echo "[1/4] Checking firewall status..."
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Temporarily disable firewall (safest for local network)
echo ""
echo "[2/4] Temporarily disabling firewall..."
echo "(Will re-enable after EDR deployment completes)"
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off

# Verify it's off
echo ""
echo "[3/4] Verifying firewall is disabled..."
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Test connection
echo ""
echo "[4/4] Testing NAS connection..."
if ping -c 1 -W 2 192.168.1.80 >/dev/null 2>&1; then
    echo "✅ Can now reach NAS!"
    echo ""
    echo "Now run the deployment script:"
    echo "  ~/Security/hybrid-edr/nas-deployment-clean/complete_via_ssh.sh"
    echo ""
    echo "After deployment completes, re-enable firewall:"
    echo "  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on"
else
    echo "⚠️  Still cannot reach NAS. This might be Starlink-level isolation."
    echo "Try connecting via ethernet cable instead."
fi
