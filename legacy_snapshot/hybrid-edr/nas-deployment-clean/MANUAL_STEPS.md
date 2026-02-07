# Complete NAS EDR via DSM Web Interface

## Step 1: Create Data Folder (30 seconds)
1. Open **File Station** in DSM
2. Navigate to: `Docker/edr/`
3. Click **Create** → **Create folder**
4. Name it: `data`
5. Verify you now have:
   - ✅ `ollama-data/` folder
   - ✅ `data/` folder
   - ✅ `docker-compose.yml` file
   - ✅ `edr_collector.py` file

## Step 2: Start Containers (1 minute)
1. Open **Container Manager** in DSM
2. Go to **Project** tab
3. Find and select `edr` project
4. Click **Action** → **Start**
5. Wait for status to show both containers running (green indicators):
   - `edr-ollama`
   - `edr-collector`

## Step 3: Download AI Model (5-10 minutes)
1. In **Container Manager** → **Container** tab
2. Click on `edr-ollama` container
3. Click **Terminal** button → **Create** → **Launch with command**: `bash` or `/bin/bash`
4. In the terminal window that opens, type:
   ```bash
   ollama pull qwen2.5:7b
   ```
5. Press Enter and wait for download (~4GB, takes 5-10 min depending on connection)
6. When complete, you'll see: "success"

## Step 4: Verify (1 minute)
1. Go back to **Container** tab
2. Click on `edr-collector` → **Logs**
3. You should see:
   ```
   EDR monitoring started
   Scanning processes...
   ```
4. Click on `edr-ollama` → **Logs**
5. You should see:
   ```
   Listening on [::]:11434
   ```

## Done! 🎉
Your NAS EDR is now running and protecting your backend services 24/7.

### Troubleshooting
- **Containers won't start**: Check logs for "bind mount" errors
  - Fix: Verify folders exist in File Station
- **Model download fails**: Check NAS internet connection
- **Collector shows errors**: Ollama model might not be downloaded yet
