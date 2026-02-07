#!/bin/bash
#
# Auto-mount BCAM NAS shares with retry logic
# Used by LaunchAgent to ensure NAS is always available
#

NAS_IP="192.168.0.80"
NAS_USER="garrylewis"
SHARES=("Apps" "Data" "Docker")
LOG_FILE="/Users/garrylewis/Security/hybrid-edr/logs/nas_mount.log"
MAX_RETRIES=3
RETRY_DELAY=5

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check if NAS is reachable
check_nas_connectivity() {
    if ping -c 1 -W 2 "$NAS_IP" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Mount a single share with retry logic
mount_share() {
    local share="$1"
    local mount_point="/Volumes/$share"
    
    # Check if already mounted
    if [ -d "$mount_point" ] && mount | grep -q "on $mount_point"; then
        log "✅ $share already mounted at $mount_point"
        return 0
    fi
    
    # Try to mount with retries
    for attempt in $(seq 1 $MAX_RETRIES); do
        log "⏳ Mounting $share (attempt $attempt/$MAX_RETRIES)..."
        
        if osascript -e "mount volume \"smb://${NAS_USER}@${NAS_IP}/${share}\"" 2>/dev/null; then
            log "✅ $share mounted successfully"
            return 0
        else
            log "❌ $share mount failed (attempt $attempt/$MAX_RETRIES)"
            if [ $attempt -lt $MAX_RETRIES ]; then
                sleep $RETRY_DELAY
            fi
        fi
    done
    
    log "❌ Failed to mount $share after $MAX_RETRIES attempts"
    return 1
}

# Main execution
log "=========================================="
log "Starting NAS auto-mount"

# Check NAS connectivity first
if ! check_nas_connectivity; then
    log "⚠️  NAS at $NAS_IP is not reachable"
    log "Skipping mount attempts"
    exit 1
fi

log "✅ NAS at $NAS_IP is reachable"

# Mount all shares
mounted=0
failed=0

for share in "${SHARES[@]}"; do
    if mount_share "$share"; then
        ((mounted++))
    else
        ((failed++))
    fi
done

# Summary
log "📊 Summary: $mounted mounted, $failed failed"

if [ $failed -eq 0 ]; then
    log "✅ All NAS shares mounted successfully"
    exit 0
else
    log "⚠️  Some shares failed to mount"
    exit 1
fi
