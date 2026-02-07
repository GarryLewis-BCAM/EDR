#!/bin/bash
set -e

# NAS EDR Deployment Script
# Deploys AI-powered EDR to Synology DS225+ NAS

NAS_IP="${NAS_IP:-192.168.1.80}"
NAS_USER="${NAS_USER:-admin}"
NAS_PATH="/volume1/Docker/edr"

echo "================================================"
echo "  🛡️  NAS EDR Deployment"
echo "================================================"
echo "Target: $NAS_USER@$NAS_IP:$NAS_PATH"
echo ""

# Check prerequisites
echo "[1/6] Checking prerequisites..."
if [ ! -f "../utils/db_v2.py" ]; then
    echo "❌ Error: Run this from nas-deployment directory"
    exit 1
fi

if ! command -v ssh &> /dev/null; then
    echo "❌ Error: SSH not found"
    exit 1
fi

# Prepare files
echo "[2/6] Preparing deployment files..."
rm -rf ./utils ./collectors ./config 2>/dev/null || true
cp -r ../utils .
cp -r ../collectors .
cp -r ../config .
cp ../edr_collector_v2.py ./edr_collector_nas.py

echo "✓ Files prepared"

# Create .env if not exists
if [ ! -f .env ]; then
    echo "[3/6] Creating .env file..."
    read -p "Twilio Account SID: " TWILIO_SID
    read -p "Twilio Auth Token: " TWILIO_TOKEN
    read -p "WhatsApp To (e.g., +61XXXXXXXXX): " WHATSAPP_TO
    
    cat > .env << EOF
TWILIO_ACCOUNT_SID=$TWILIO_SID
TWILIO_AUTH_TOKEN=$TWILIO_TOKEN
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:$WHATSAPP_TO
EOF
    echo "✓ Created .env"
else
    echo "[3/6] Using existing .env file"
fi

# Test NAS connection
echo "[4/6] Testing NAS connection..."
if ! ssh -o ConnectTimeout=5 $NAS_USER@$NAS_IP "echo connected" &>/dev/null; then
    echo "❌ Error: Cannot connect to NAS at $NAS_IP"
    echo "   Make sure SSH is enabled in DSM"
    exit 1
fi
echo "✓ Connected to NAS"

# Transfer files
echo "[5/6] Transferring files to NAS..."
ssh $NAS_USER@$NAS_IP "mkdir -p $NAS_PATH"
rsync -avz --exclude='.git' --exclude='*.pyc' --exclude='__pycache__' \
    . $NAS_USER@$NAS_IP:$NAS_PATH/

echo "✓ Files transferred"

# Deploy on NAS
echo "[6/6] Deploying Docker stack..."
ssh $NAS_USER@$NAS_IP << 'ENDSSH'
cd /volume1/Docker/edr

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker not found. Install Container Manager in DSM Package Center"
    exit 1
fi

# Pull images
echo "  → Pulling Docker images..."
docker-compose pull

# Start Ollama first
echo "  → Starting Ollama..."
docker-compose up -d ollama
sleep 10

# Download AI model (qwen2.5:7b is smaller, good for NAS)
echo "  → Downloading AI model (this may take 5-10 mins)..."
docker exec edr-ollama ollama pull qwen2.5:7b || echo "Model download started in background"

# Start all services
echo "  → Starting all services..."
docker-compose up -d

# Wait for services
sleep 5

# Check status
echo ""
echo "================================================"
echo "  ✅ Deployment Complete!"
echo "================================================"
docker-compose ps

echo ""
echo "Services:"
echo "  • Dashboard: http://$NAS_IP:5050"
echo "  • Ollama AI: http://$NAS_IP:11434"
echo ""
echo "Next steps:"
echo "  1. Wait 5-10 mins for AI model download to complete"
echo "  2. Check logs: docker logs -f edr-collector"
echo "  3. Access dashboard: http://$NAS_IP:5050"
echo ""
ENDSSH

echo ""
echo "🎉 Your NAS is now protected 24/7!"
echo ""
echo "Monitor:"
echo "  ssh $NAS_USER@$NAS_IP 'docker logs -f edr-collector'"
echo ""
echo "Dashboard:"
echo "  http://$NAS_IP:5050"
echo ""
