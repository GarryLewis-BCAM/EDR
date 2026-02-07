#!/bin/bash
# Complete NAS EDR Deployment Automation
# This script finishes the EDR setup on your Synology NAS

set -e

NAS_IP="192.168.1.80"
NAS_USER="garrylewis"
EDR_PATH="/volume1/Docker/edr"

echo "=========================================="
echo "NAS EDR Deployment - Final Steps"
echo "=========================================="

# Test connectivity
echo "[1/5] Testing NAS connectivity..."
if ! ping -c 1 -W 2 $NAS_IP &>/dev/null; then
    echo "❌ Cannot reach NAS at $NAS_IP"
    echo "Please ensure:"
    echo "  - NAS is powered on"
    echo "  - You're on the same network"
    echo "  - IP address is correct"
    exit 1
fi
echo "✅ NAS is reachable"

# Try SSH (if enabled)
echo ""
echo "[2/5] Checking SSH access..."
if ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no $NAS_USER@$NAS_IP "echo 'SSH OK'" 2>/dev/null; then
    echo "✅ SSH access available - using automated method"
    
    # Create missing data folder
    echo ""
    echo "[3/5] Creating data folder..."
    ssh $NAS_USER@$NAS_IP "mkdir -p $EDR_PATH/data && chmod 755 $EDR_PATH/data"
    echo "✅ Folder created"
    
    # Verify folder structure
    echo ""
    echo "[4/5] Verifying folder structure..."
    ssh $NAS_USER@$NAS_IP "ls -la $EDR_PATH/" | grep -E "(ollama-data|data|docker-compose.yml)"
    
    # Start containers using docker compose
    echo ""
    echo "[5/5] Starting EDR containers..."
    ssh $NAS_USER@$NAS_IP "cd $EDR_PATH && docker-compose up -d"
    
    # Wait for containers to start
    sleep 5
    
    # Download AI model
    echo ""
    echo "[BONUS] Downloading AI model (this may take 5-10 minutes)..."
    ssh $NAS_USER@$NAS_IP "docker exec edr-ollama ollama pull qwen2.5:7b"
    
    echo ""
    echo "=========================================="
    echo "✅ NAS EDR DEPLOYMENT COMPLETE!"
    echo "=========================================="
    echo ""
    echo "EDR is now protecting your NAS at http://$NAS_IP:11434"
    echo ""
    echo "Check status:"
    echo "  docker ps"
    echo "  docker logs edr-collector"
    echo "  docker logs edr-ollama"
    
else
    echo "⚠️  SSH not available - manual steps required"
    echo ""
    echo "=========================================="
    echo "MANUAL COMPLETION STEPS"
    echo "=========================================="
    echo ""
    echo "Step 1: Create Data Folder"
    echo "  1. Open File Station on NAS web interface"
    echo "  2. Navigate to: /Docker/edr/"
    echo "  3. Create new folder named: data"
    echo ""
    echo "Step 2: Start Containers"
    echo "  1. Open Container Manager"
    echo "  2. Go to Project tab"
    echo "  3. Select 'edr' project"
    echo "  4. Click Action → Start"
    echo ""
    echo "Step 3: Download AI Model"
    echo "  1. In Container Manager → Container tab"
    echo "  2. Select 'edr-ollama' container"
    echo "  3. Click Terminal → Create → Launch"
    echo "  4. Run: ollama pull qwen2.5:7b"
    echo ""
    echo "Visit: http://$NAS_IP:5000"
    echo "=========================================="
fi
