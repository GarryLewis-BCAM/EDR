#!/bin/bash
#
# BCAM EDR - iPad Remote Access Quick Setup
# This script helps you set up Tailscale for secure remote access
#

echo "🛡️  BCAM EDR - iPad Remote Access Setup"
echo "========================================="
echo ""

# Check if Tailscale is installed
if command -v tailscale &> /dev/null; then
    echo "✅ Tailscale is already installed"
    
    # Check if running
    if tailscale status &> /dev/null; then
        echo "✅ Tailscale is running"
        
        # Get Tailscale IP
        TAILSCALE_IP=$(tailscale ip -4)
        echo ""
        echo "📱 Your Tailscale IP: $TAILSCALE_IP"
        echo ""
        echo "🌐 Dashboard URLs:"
        echo "   Local:     http://localhost:5050"
        echo "   Network:   http://192.168.1.93:5050"
        echo "   Tailscale: http://$TAILSCALE_IP:5050"
        echo ""
        echo "📋 Next steps for iPad:"
        echo "   1. Install Tailscale from App Store"
        echo "   2. Sign in with same account"
        echo "   3. Open Safari and go to: http://$TAILSCALE_IP:5050"
        echo "   4. Add to Home Screen (Share → Add to Home Screen)"
        echo ""
        
        # Test dashboard accessibility
        echo "🔍 Testing dashboard access via Tailscale..."
        if curl -s -o /dev/null -w "%{http_code}" http://$TAILSCALE_IP:5050 | grep -q "200"; then
            echo "✅ Dashboard is accessible via Tailscale!"
        else
            echo "⚠️  Dashboard may not be running. Start it with:"
            echo "   cd ~/Security/hybrid-edr && nohup python3 dashboard/app.py &"
        fi
        
    else
        echo "⚠️  Tailscale is installed but not running"
        echo ""
        echo "To start Tailscale:"
        echo "  1. Open Applications folder"
        echo "  2. Double-click Tailscale"
        echo "  3. Sign in with Google/Microsoft/GitHub"
        echo "  4. Run this script again"
    fi
else
    echo "❌ Tailscale is not installed"
    echo ""
    echo "📦 Installing Tailscale..."
    echo ""
    echo "Option 1 (Homebrew - RECOMMENDED):"
    echo "  brew install --cask tailscale"
    echo ""
    echo "Option 2 (Direct Download):"
    echo "  1. Visit: https://tailscale.com/download/mac"
    echo "  2. Download and install Tailscale"
    echo "  3. Run this script again"
    echo ""
    
    read -p "Install via Homebrew now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install --cask tailscale
        echo ""
        echo "✅ Tailscale installed!"
        echo ""
        echo "🚀 Next steps:"
        echo "  1. Open Tailscale from Applications"
        echo "  2. Sign in to create your private network"
        echo "  3. Run this script again to get your Tailscale IP"
    fi
fi

echo ""
echo "📖 Full guide: ~/Security/hybrid-edr/IPAD_REMOTE_ACCESS.md"
echo ""
