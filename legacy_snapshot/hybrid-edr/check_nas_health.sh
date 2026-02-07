#!/bin/bash
#
# NAS Health Check for EDR
# Validates NAS shares are mounted and accessible
# Returns non-zero exit code if issues detected
#

NAS_IP="192.168.1.80"
REQUIRED_SHARES=("Apps" "Data" "Docker")
CRITICAL_PATHS=(
    "/Volumes/Data/Logs/Security/edr"
    "/Volumes/Apps/Services/EDR/backups"
)

check_share_mounted() {
    local share="$1"
    local mount_point="/Volumes/$share"
    
    if [ -d "$mount_point" ] && mount | grep -q "on $mount_point"; then
        return 0
    else
        return 1
    fi
}

check_path_writable() {
    local path="$1"
    
    if [ -d "$path" ] && [ -w "$path" ]; then
        return 0
    else
        return 1
    fi
}

# Main health check
issues=0

# Check NAS connectivity
if ! ping -c 1 -W 2 "$NAS_IP" > /dev/null 2>&1; then
    echo "❌ NAS at $NAS_IP is not reachable"
    ((issues++))
else
    echo "✅ NAS is reachable"
fi

# Check each share
for share in "${REQUIRED_SHARES[@]}"; do
    if check_share_mounted "$share"; then
        echo "✅ $share is mounted"
    else
        echo "❌ $share is NOT mounted"
        ((issues++))
    fi
done

# Check critical paths
for path in "${CRITICAL_PATHS[@]}"; do
    if check_path_writable "$path"; then
        echo "✅ $path is accessible and writable"
    else
        echo "❌ $path is not accessible or not writable"
        ((issues++))
    fi
done

# Summary
echo ""
if [ $issues -eq 0 ]; then
    echo "✅ NAS health check passed"
    exit 0
else
    echo "⚠️  NAS health check failed: $issues issue(s) detected"
    exit 1
fi
