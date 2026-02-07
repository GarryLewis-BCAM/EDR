# Research Report: Database Growth & Uptime Display Issues
## Investigation Date: 2025-12-04 07:55 AM

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ISSUE 1: RAPID DATABASE GROWTH

### Current Status
- **Database Size:** 1.5 GB (edr.db) + 19 MB (WAL) + 9.5 MB (SHM) = **~1.54 GB total**
- **Time Since Cleanup:** ~3.19 hours
- **Growth Rate:** 8.26 MB → 1.54 GB in 3.19 hours
- **Growth Speed:** ~481 MB/hour

### Root Cause Analysis

**The Problem:**
SQLite is in WAL (Write-Ahead Logging) mode, which is EXCELLENT for concurrent writes but has a critical issue:

**WAL files don't auto-checkpoint aggressively enough.**

#### What's Happening:
1. Collector writes events to WAL file (edr.db-wal)
2. WAL grows to 19 MB before checkpoint
3. Main DB has 1,356,255 process events (3.19 hours of data)
4. **Insertion Rate: 425,439 events/hour**
5. **Projected 24h growth: 10.2 MILLION events**

#### Why Cleanup Didn't Help:
The cleanup script runs VACUUM which:
- ✅ Deletes old rows from main DB
- ✅ Reclaims space
- ❌ **BUT** new events are being inserted at 425K/hour!

**After cleanup at 3:47 PM:**
- Started: 8.26 MB
- Now (6:57 PM): 1.54 GB (3.19 hours later)
- Rate: 481 MB/hour

#### The Math:
```
Current rate: 425,439 events/hour
Database size: 1.54 GB for 3.19 hours of data
Average: ~483 MB/hour growth

Daily projection:
- Events: 10.2 million
- Size: ~11.6 GB/day
```

**This explains why database was 11.7 GB before cleanup - it was ~24 hours of data!**

### The REAL Problem:

**The retention policies are working CORRECTLY, but the event collection rate is TOO HIGH.**

#### Current Retention:
- Process events: 30 days
- Network events: 7 days
- File events: 14 days

#### At current rate (425K events/hour):
- 30 days of process events = **306 MILLION events**
- Estimated size: **~350 GB**

**This is unsustainable.**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Why Is Collection Rate So High?

Need to investigate collector configuration:
1. Is it polling too frequently?
2. Is it collecting duplicate events?
3. Are there processes creating excessive events?
4. Is deduplication working?

Let me check the collector interval and event types:

**Collector Statistics (from DB):**
- Total events: 1,356,255 in 3.19 hours
- Process events: 1,356,255
- Network events: 17,014
- File events: 2,005

**Process events dominate:** 99.9% of all events

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Technical Details: SQLite WAL Mode

**Current Configuration:**
- Journal mode: WAL (Write-Ahead Logging)
- Auto-checkpoint: 1000 pages
- Current DB size: 1579 MB (internal calculation)
- Page size: 4096 bytes

**WAL Behavior:**
- Writes go to WAL file first
- Checkpoint moves WAL → main DB
- Auto-checkpoint at 1000 pages (4 MB)
- But with heavy writes, WAL can grow larger

**The WAL file is 19 MB** - this means ~5000 pages of uncommitted writes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ISSUE 2: UPTIME DISPLAY STUCK AT "<1 hour"

### Current Status
- **Collector Actual Uptime:** 6 hours 31 minutes (started 12:26:58 PM)
- **Dashboard Displayed Uptime:** "<1 hour" (stuck)

### Root Cause Analysis

**The Bug (app.py line 954):**
```python
health['uptime_seconds'] = datetime.now().timestamp() - last_event + 30  # Approximate
```

**This calculates:** `now - last_event_timestamp + 30`

**The Problem:**
- `last_event` is the timestamp of the MOST RECENT event
- If collector is actively running, `last_event` is always ~0-30 seconds ago
- So `uptime_seconds` = `now - (now - 30s) + 30` = **~30-60 seconds**
- This will ALWAYS show "<1 hour"

**What it SHOULD calculate:**
The uptime should be based on:
1. Collector process start time (from process info), OR
2. Oldest event timestamp in database (collector's first event), OR
3. Stored start time in a config/state file

**Current Logic is Backwards:**
- Uses NEWEST event → shows time since last event (~30s)
- Should use OLDEST event or process start time → shows actual uptime

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## PROPOSED SOLUTIONS

### Solution 1: Database Growth

**Option A: Reduce Retention Periods (Quick Fix)**
- Process events: 30 days → **3 days**
- Network events: 7 days → **2 days**
- File events: 14 days → **3 days**

**Impact:**
- 3 days at 425K/hour = ~30M events
- Estimated size: ~35 GB → still too large
- **Not sufficient - need Option B**

**Option B: Reduce Collection Rate (Proper Fix)**

**Investigate and fix:**
1. Check collector polling interval (should be 5-10s, not 1s)
2. Add process deduplication (don't log same process multiple times)
3. Filter out high-frequency processes (system daemons)
4. Add sampling for low-priority processes

**Specific Changes Needed:**
1. Read collector config to see polling interval
2. Check if deduplication is enabled
3. Add process blacklist for noisy system processes
4. Consider sampling: log 1 in 10 events for low-threat processes

**Expected Result:**
- Reduce rate from 425K/hour → ~50K/hour (85% reduction)
- 30 days of data = ~36M events
- Estimated size: ~40 GB (still needs Option C)

**Option C: More Aggressive Retention (Combined Fix)**
- Process events: 30 days → **7 days**
- Network events: 7 days → **3 days**
- File events: 14 days → **7 days**
- Alerts: 90 days → **30 days**

**With Option B + C:**
- 7 days at 50K/hour = ~8.4M events
- Estimated size: ~10 GB
- **This is sustainable**

**Option D: Add WAL Checkpointing**
- Force checkpoint every 5 minutes
- Prevent WAL from growing too large
- This is a band-aid but helps

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Solution 2: Uptime Display

**Fix app.py line 954:**

**Current (WRONG):**
```python
health['uptime_seconds'] = datetime.now().timestamp() - last_event + 30  # Approximate
```

**Fixed (CORRECT):**
```python
# Get collector start time from oldest event in database
cursor.execute('SELECT MIN(timestamp) FROM process_events')
first_event = cursor.fetchone()[0]

if first_event:
    health['uptime_seconds'] = datetime.now().timestamp() - first_event
else:
    health['uptime_seconds'] = 0
```

**Alternative Fix (Using Process Info):**
```python
# Get collector PID and check process start time
import psutil
try:
    # Find collector process
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        if 'edr_collector_v2.py' in ' '.join(proc.info.get('cmdline', [])):
            health['uptime_seconds'] = datetime.now().timestamp() - proc.info['create_time']
            break
except:
    health['uptime_seconds'] = 0
```

**Recommendation:** Use process info (more accurate, doesn't depend on DB)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## RECOMMENDED ACTION PLAN

### Phase 1: Immediate Fixes (Today)
1. **Fix uptime display** (5 min) - Use process start time
2. **Add WAL checkpointing** (10 min) - Force checkpoint every 5 min
3. **More aggressive retention** (5 min) - 7-day window instead of 30

### Phase 2: Investigate Collection Rate (Next Session)
1. Read collector config and source code
2. Check polling interval
3. Identify high-frequency processes
4. Design deduplication/sampling strategy

### Phase 3: Implement Rate Reduction (After Investigation)
1. Add process blacklist
2. Implement deduplication
3. Add sampling for low-priority events
4. Target: 85% reduction (425K → 50K events/hour)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## QUESTIONS FOR USER

Before implementing fixes:

1. **Do you want aggressive retention (7 days) or keep 30 days?**
   - 7 days = ~10 GB (with rate reduction)
   - 30 days = ~40 GB (with rate reduction)

2. **What processes are running that generate so many events?**
   - Need to identify noisy processes to filter

3. **What's acceptable database size?**
   - Current: 1.54 GB/3 hours → 11.6 GB/day
   - Target: Under 20 GB? Under 50 GB?

4. **Priority: Storage space or historical data?**
   - More history = more disk space
   - Less history = smaller DB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## SUMMARY

### Issue 1: Database Growth
**Root Cause:** Collection rate too high (425K events/hour)
**Not a Bug:** Cleanup is working, but new data comes in faster
**Solution:** Reduce collection rate + shorter retention

### Issue 2: Uptime Display
**Root Cause:** Logic error - uses newest event instead of oldest
**Is a Bug:** Calculation is backwards
**Solution:** Use process start time or oldest event timestamp

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Ready to implement fixes after user confirmation on retention period and priority.**
