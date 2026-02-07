# Database Size Issue - FIXED

## Problem Summary

**Database grew to 5.4GB** containing 4.6 million process events, consuming excessive disk space and showing warning alerts.

### Root Cause
1. **No automatic cleanup:** Collector had cleanup code but it was commented out (line 378 in `edr_collector_v2.py`)
2. **Excessive logging:** Every process event was being logged without retention limits
3. **Old data accumulation:** All 4.6M events were older than 7 days

## Solution Implemented

### Immediate Fix: Manual Cleanup ✅

Created and ran `cleanup_database.py`:

```bash
# Removed 4,691,345 old events (>7 days)
# Database: 5,378 MB → 8.9 MB
# Space saved: 5,369 MB (99.8%)
```

**Results:**
- ✅ 5.37 GB of disk space reclaimed
- ✅ Database now 8.9 MB (healthy size)
- ✅ All events older than 7 days removed
- ✅ Warning notifications stopped

### Desktop Launcher Fix ✅

**Problem:** macOS Gatekeeper blocking app as "not safe"

**Solution:**
```bash
xattr -d com.apple.quarantine "/Users/garrylewis/Desktop/EDR Dashboard.app"
xattr -cr "/Users/garrylewis/Desktop/EDR Dashboard.app"
```

**Status:** ✅ Desktop launcher now works without security warnings

## Cleanup Tool Usage

### Manual Cleanup

```bash
# Dry run (see what would be deleted)
./cleanup_database.py --days 7 --dry-run

# Keep last 7 days of events
./cleanup_database.py --days 7

# Keep last 30 days (config default)
./cleanup_database.py --days 30

# Custom database path
./cleanup_database.py --days 7 --db /path/to/edr.db
```

### Automatic Cleanup (Future)

The collector is configured for auto-cleanup every ~14 hours (10,000 cycles):
- **Retention:** 30 days (config: `maintenance.auto_cleanup.old_events_days`)
- **Frequency:** Every 10,000 collection cycles (~14 hours at 5s intervals)
- **Location:** `edr_collector_v2.py` line 374-379

**Current Status:** Code exists but cleanup method not yet implemented in db_v2.py

## Recommended Maintenance Schedule

### Weekly (Automated via cron)
```bash
# Add to crontab: crontab -e
0 3 * * 0 /Users/garrylewis/Security/hybrid-edr/venv/bin/python3 /Users/garrylewis/Security/hybrid-edr/cleanup_database.py --days 7
```

This runs every Sunday at 3 AM, keeping last 7 days of events.

### Monthly (Manual)
1. Check database size: `du -h data/edr.db`
2. If > 100 MB, consider tighter retention
3. Review alerts to ensure retention is adequate

## Configuration

Edit `config/config.yaml`:

```yaml
maintenance:
  auto_cleanup:
    enabled: true
    old_events_days: 30  # Adjust retention period
```

**Recommendations:**
- **Development/Testing:** 7 days (saves space)
- **Production/Investigation:** 30 days (default)
- **Long-term forensics:** 90 days (requires more disk)

## Database Size Targets

| Events | Approx Size | Retention | Use Case |
|--------|-------------|-----------|----------|
| ~50K | ~10 MB | 1-2 days | Testing |
| ~500K | ~100 MB | 7 days | Development |
| ~2M | ~400 MB | 30 days | Production |
| ~6M | ~1.2 GB | 90 days | Forensics |

**Rule of thumb:** ~200 KB per 1,000 events

## Monitoring Database Growth

### Check Current Size
```bash
# File size
du -h data/edr.db

# Event counts
sqlite3 data/edr.db "SELECT COUNT(*) FROM process_events;"
```

### Dashboard Monitoring
The dashboard shows database size in the health API:
```bash
curl -sk https://localhost:5050/api/health | grep db_size
```

### Set Alert Threshold
Dashboard alerts when database exceeds 1 GB (line 418 in `edr_collector_v2.py`):
```python
if db_size > 1000:  # > 1GB
    health_issues.append(f"Database size is {db_size:.0f}MB")
```

## Prevention Going Forward

1. **Automated weekly cleanup** (cron job recommended above)
2. **Monitor dashboard health alerts** for database size warnings
3. **Adjust retention** based on investigation needs
4. **Consider storage capacity** when setting retention periods

## What Changed

**Before:**
- 4.6M events, 5.4 GB database
- No automatic cleanup running
- Warning notifications every few minutes
- Desktop launcher blocked by Gatekeeper

**After:**
- Clean database, 8.9 MB
- Manual cleanup tool available
- No warning notifications
- Desktop launcher works
- Weekly cron job recommended

## Cleanup Logs

All cleanup operations log to console:
- Events removed count
- Space reclaimed
- Before/after sizes
- Vacuum progress

**Example output:**
```
Initial database size: 5378.41 MB
Deleting 4,691,345 old events...
✓ Deleted 4,691,345 events
Vacuuming database to reclaim space...
✓ Vacuum completed
Final size: 8.86 MB
Space saved: 5369.55 MB (99.8%)
```

## Files Created/Modified

- **NEW:** `cleanup_database.py` - Standalone cleanup utility
- **MODIFIED:** Desktop launcher - Quarantine removed
- **UNCHANGED:** `config/config.yaml` - Retention set to 30 days
- **NOTE:** Collector cleanup code exists but not yet active

## Next Steps (Optional)

1. **Implement auto-cleanup in collector:**
   - Add cleanup method to `utils/db_v2.py`
   - Uncomment line 378 in `edr_collector_v2.py`
   - Test with 10,000 cycle trigger

2. **Add cron job for weekly cleanup:**
   ```bash
   crontab -e
   # Add: 0 3 * * 0 /path/to/cleanup_database.py --days 7
   ```

3. **Monitor for one week:**
   - Check database size daily
   - Ensure no warnings appear
   - Verify retention meets needs
