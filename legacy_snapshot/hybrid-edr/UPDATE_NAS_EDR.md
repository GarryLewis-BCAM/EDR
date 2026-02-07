# Update NAS EDR with Improved Dependency Management

## Why Update?

The NAS EDR currently has:
- ❌ Inline pip install in docker-compose (harder to maintain)
- ❌ Missing dependencies (no ML features, no flask-socketio)
- ❌ No version pinning (can break on updates)

After update, you'll have:
- ✅ Proper `requirements.txt` with all dependencies
- ✅ Version-controlled dependencies
- ✅ ML capabilities (if needed)
- ✅ WebSocket support for real-time updates
- ✅ Easier to update and maintain

## Update Steps

### 1. Copy Updated Files to NAS

```bash
# From your Mac
cd ~/Security/hybrid-edr

# Copy new requirements.txt
scp nas-requirements.txt admin@192.168.1.80:/volume1/Docker/edr/requirements.txt

# Copy updated docker-compose.yml
scp docker-compose-updated.yml admin@192.168.1.80:/volume1/Docker/edr/docker-compose.yml
```

### 2. Restart NAS EDR Container

```bash
# SSH into NAS
ssh admin@192.168.1.80

# Navigate to EDR directory
cd /volume1/Docker/edr

# Stop current container
docker-compose down

# Start with new configuration
docker-compose up -d

# Watch logs to verify successful start
docker-compose logs -f edr-collector
```

Expected output:
```
edr-collector | Collecting watchdog>=6.0.0
edr-collector | Successfully installed watchdog-6.0.0 flask-socketio-5.4.1 ...
edr-collector | Starting EDR collector...
```

### 3. Verify Installation

```bash
# Check container is running
docker-compose ps

# Verify watchdog is installed
docker exec edr-collector pip list | grep watchdog
# Should show: watchdog    6.0.0

# Check container health
docker inspect edr-collector | grep -A5 Health
```

## What Changed?

### Old docker-compose.yml:
```yaml
command: >
  sh -c "pip install --quiet --upgrade pip &&
         pip install --quiet psutil pyyaml requests twilio ollama watchdog &&
         python3 /app/edr_collector_nas.py"
```

### New docker-compose.yml:
```yaml
command: >
  sh -c "pip install --quiet --upgrade pip &&
         pip install --quiet -r /app/requirements.txt &&
         python3 /app/edr_collector_nas.py"
```

**Benefits:**
- Single source of truth for dependencies (`requirements.txt`)
- Easy to add/remove packages
- Version control friendly
- Matches local Mac environment

## Differences: Mac vs NAS EDR

| Aspect | Mac EDR | NAS EDR |
|--------|---------|---------|
| **Python Environment** | Virtual environment (venv) | Docker container |
| **Dependency Installation** | One-time (persists) | Every container start |
| **Launch Method** | `./start_collector.sh` | `docker-compose up` |
| **Watchdog Issue** | ✅ Fixed (use venv) | ✅ Not affected (Docker) |

**Key Point:** The NAS EDR doesn't have the watchdog disappearing problem because Docker containers are ephemeral - dependencies are reinstalled fresh every time. However, using `requirements.txt` is still better practice.

## Rollback (If Needed)

If something goes wrong:

```bash
# On NAS
cd /volume1/Docker/edr

# Restore old inline pip install
docker-compose down

# Edit docker-compose.yml to use old command
nano docker-compose.yml

# Change back to:
# pip install --quiet psutil pyyaml requests twilio ollama watchdog

# Restart
docker-compose up -d
```

## Optional: Add ML Capabilities

The new `requirements.txt` includes scikit-learn, pandas, and numpy. If you want to enable ML-based threat detection on NAS:

1. Copy ML training utilities from Mac:
```bash
scp -r utils/ml_training.py admin@192.168.1.80:/volume1/Docker/edr/utils/
```

2. The container will automatically have ML libraries available

## Monitoring

After update, monitor for 24 hours:

```bash
# Check logs periodically
docker-compose logs --tail=100 -f edr-collector

# Check resource usage
docker stats edr-collector

# Verify file monitoring is active
docker-compose logs edr-collector | grep "File monitor"
```

## Questions?

- If watchdog-related errors occur: Check `/volume1/Docker/edr/requirements.txt` exists
- If container won't start: Check `docker-compose logs edr-collector` for Python errors
- If missing dependencies: Verify all lines in `requirements.txt` have versions specified
