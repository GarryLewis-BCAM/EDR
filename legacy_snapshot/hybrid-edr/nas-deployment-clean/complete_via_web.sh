#!/bin/bash
# Complete NAS EDR via Synology Web UI using cURL API calls

NAS_IP="192.168.1.80"
NAS_USER="garrylewis"
NAS_PASS="${NAS_PASSWORD}"  # Set this before running

echo "=========================================="
echo "NAS EDR Web API Completion"
echo "=========================================="

# Step 1: Login and get session ID
echo "[1/4] Logging into NAS..."
LOGIN_RESPONSE=$(curl -s "http://${NAS_IP}:5000/webapi/auth.cgi" \
  --data "api=SYNO.API.Auth&version=3&method=login&account=${NAS_USER}&passwd=${NAS_PASS}&session=FileStation&format=cookie")

if echo "$LOGIN_RESPONSE" | grep -q '"success":true'; then
    echo "✅ Login successful"
    SID=$(echo "$LOGIN_RESPONSE" | grep -o '"sid":"[^"]*"' | cut -d'"' -f4)
else
    echo "❌ Login failed. Check credentials."
    echo "$LOGIN_RESPONSE"
    exit 1
fi

# Step 2: Create data folder
echo ""
echo "[2/4] Creating /volume1/Docker/edr/data folder..."
CREATE_FOLDER=$(curl -s "http://${NAS_IP}:5000/webapi/entry.cgi" \
  --cookie "id=$SID" \
  --data "api=SYNO.FileStation.CreateFolder&version=2&method=create&folder_path=/Docker/edr&name=data")

if echo "$CREATE_FOLDER" | grep -q '"success":true'; then
    echo "✅ Folder created successfully"
else
    echo "⚠️  Folder may already exist or creation failed"
    echo "$CREATE_FOLDER"
fi

# Step 3: Start Docker containers using Container Manager API
echo ""
echo "[3/4] Starting EDR containers..."
START_CONTAINER=$(curl -s "http://${NAS_IP}:5000/webapi/entry.cgi" \
  --cookie "id=$SID" \
  --data "api=SYNO.Docker.Project&version=1&method=start&project=edr")

if echo "$START_CONTAINER" | grep -q '"success":true'; then
    echo "✅ Containers starting..."
    sleep 10
else
    echo "⚠️  Container start may have failed. Check Container Manager UI."
    echo "$START_CONTAINER"
fi

# Step 4: Pull AI model
echo ""
echo "[4/4] Downloading AI model (qwen2.5:7b)..."
echo "This will take 5-10 minutes..."

PULL_MODEL=$(curl -s "http://${NAS_IP}:5000/webapi/entry.cgi" \
  --cookie "id=$SID" \
  --data "api=SYNO.Docker.Container&version=1&method=exec_create&name=edr-ollama&command=ollama pull qwen2.5:7b")

if echo "$PULL_MODEL" | grep -q '"success":true'; then
    echo "✅ Model download started"
else
    echo "⚠️  Model download may have failed"
    echo "$PULL_MODEL"
fi

# Logout
curl -s "http://${NAS_IP}:5000/webapi/auth.cgi?api=SYNO.API.Auth&version=1&method=logout&session=FileStation" \
  --cookie "id=$SID" > /dev/null

echo ""
echo "=========================================="
echo "Deployment steps completed via API"
echo "=========================================="
echo ""
echo "Next: Verify in Container Manager that both containers are running"
echo "Visit: http://${NAS_IP}:5000"
