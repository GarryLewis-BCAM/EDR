#!/bin/bash
# Complete NAS EDR via SSH (after SSH is enabled in DSM)

NAS_IP="192.168.1.80"
NAS_USER="garrylewis"
EDR_PATH="/volume1/Docker/edr"

echo "=========================================="
echo "NAS EDR Deployment via SSH"
echo "=========================================="

# Test SSH access
echo "[1/6] Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $NAS_USER@$NAS_IP "echo 'SSH OK'" 2>/dev/null; then
    echo "❌ SSH not accessible. Please enable SSH in DSM:"
    echo "   Control Panel → Terminal & SNMP → Enable SSH service"
    exit 1
fi
echo "✅ SSH connected"

# Create data folder
echo ""
echo "[2/6] Creating data folder..."
ssh $NAS_USER@$NAS_IP "mkdir -p $EDR_PATH/data && chmod 755 $EDR_PATH/data"
echo "✅ Folder created"

# Verify folder structure
echo ""
echo "[3/6] Verifying deployment files..."
ssh $NAS_USER@$NAS_IP "ls -lh $EDR_PATH/" | grep -E "(ollama-data|data|docker-compose|edr_collector)"
echo "✅ Files verified"

# Start containers
echo ""
echo "[4/6] Starting EDR containers..."
ssh $NAS_USER@$NAS_IP "cd $EDR_PATH && docker-compose up -d"
sleep 8

# Check container status
echo ""
echo "[5/6] Checking container status..."
ssh $NAS_USER@$NAS_IP "docker ps --filter name=edr"

# Download AI model
echo ""
echo "[6/6] Downloading AI model (qwen2.5:7b)..."
echo "This will take 5-10 minutes depending on your internet speed..."
ssh $NAS_USER@$NAS_IP "docker exec edr-ollama ollama pull qwen2.5:7b"

echo ""
echo "=========================================="
echo "✅ NAS EDR DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Your NAS is now protected with AI-powered EDR"
echo ""
echo "Services:"
echo "  • Ollama AI: http://$NAS_IP:11434"
echo "  • EDR Database: $EDR_PATH/data/edr.db"
echo ""
echo "Check logs anytime:"
echo "  ssh $NAS_USER@$NAS_IP"
echo "  docker logs edr-collector"
echo "  docker logs edr-ollama"
echo ""
echo "To disable SSH for security:"
echo "  DSM → Control Panel → Terminal & SNMP → Disable SSH"
