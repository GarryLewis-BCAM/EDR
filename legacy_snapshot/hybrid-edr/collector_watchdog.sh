#!/bin/bash
#
# EDR Collector Watchdog
# Monitors collector process and auto-restarts if crashed
# Sends alerts on crash detection
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/watchdog.log"
COLLECTOR_NAME="edr_collector_v2.py"
MAX_RESTARTS=5
RESTART_WINDOW=3600  # 1 hour
CHECK_INTERVAL=30    # Check every 30 seconds

# Track restarts
RESTART_COUNT=0
RESTART_TIMES=()

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_collector() {
    if pgrep -f "$COLLECTOR_NAME" > /dev/null; then
        return 0  # Running
    else
        return 1  # Not running
    fi
}

get_crash_reason() {
    # Check last 20 lines of collector log for error
    if [ -f "$SCRIPT_DIR/collector.log" ]; then
        tail -20 "$SCRIPT_DIR/collector.log" | grep -E "ERROR|CRITICAL|Traceback" | tail -5
    fi
}

restart_collector() {
    log "⚠️  Collector crashed! Attempting restart..."
    
    # Get crash reason
    CRASH_REASON=$(get_crash_reason)
    if [ -n "$CRASH_REASON" ]; then
        log "Crash reason: $CRASH_REASON"
    fi
    
    # Track restart time
    CURRENT_TIME=$(date +%s)
    RESTART_TIMES+=($CURRENT_TIME)
    
    # Remove restarts older than RESTART_WINDOW
    for i in "${!RESTART_TIMES[@]}"; do
        if [ $((CURRENT_TIME - RESTART_TIMES[i])) -gt $RESTART_WINDOW ]; then
            unset 'RESTART_TIMES[i]'
        fi
    done
    RESTART_TIMES=("${RESTART_TIMES[@]}")  # Re-index array
    
    RESTART_COUNT=${#RESTART_TIMES[@]}
    
    # Check if too many restarts
    if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
        log "❌ CRITICAL: Too many restarts ($RESTART_COUNT in last hour)"
        log "❌ Watchdog disabled. Manual intervention required."
        
        # Send critical alert
        echo "CRITICAL: EDR Collector crash loop detected. $RESTART_COUNT crashes in 1 hour. Manual intervention required." > /tmp/edr_critical_alert.txt
        
        exit 1
    fi
    
    # Restart using clean restart script
    log "Restarting collector (attempt $RESTART_COUNT/$MAX_RESTARTS)..."
    
    if [ -x "$SCRIPT_DIR/restart_collector_clean.sh" ]; then
        "$SCRIPT_DIR/restart_collector_clean.sh" >> "$LOG_FILE" 2>&1
    else
        # Fallback: manual restart
        cd "$SCRIPT_DIR"
        pkill -f "$COLLECTOR_NAME"
        sleep 2
        find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        nohup python3 edr_collector_v2.py > collector_startup.log 2>&1 &
    fi
    
    sleep 5
    
    if check_collector; then
        log "✓ Collector restarted successfully"
        return 0
    else
        log "❌ Restart failed"
        return 1
    fi
}

log "=========================================="
log "EDR Collector Watchdog Started"
log "=========================================="
log "Monitoring: $COLLECTOR_NAME"
log "Check interval: ${CHECK_INTERVAL}s"
log "Max restarts: $MAX_RESTARTS per hour"
log ""

# Main monitoring loop
while true; do
    if ! check_collector; then
        log "❌ Collector not running!"
        
        if ! restart_collector; then
            log "❌ Unable to restart collector. Exiting watchdog."
            exit 1
        fi
    fi
    
    sleep $CHECK_INTERVAL
done
