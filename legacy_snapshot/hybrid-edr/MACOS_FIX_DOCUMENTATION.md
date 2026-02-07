# EDR Collector MacOS Stability Fix

## Problem Summary
The EDR collector was crashing immediately upon startup due to `psutil.AccessDenied` exceptions when attempting to enumerate network connections on macOS.

## Root Cause
<cite index="4-3,11-32,17-3">On macOS, `psutil.net_connections()` requires root privileges and fails with AccessDenied unless the process is owned by root</cite>. This is a known limitation of psutil on macOS platforms that lack a proc filesystem.

### Specific Issues Identified:
1. **Network Tracker**: Called `psutil.net_connections(kind='inet')` without proper exception handling for `psutil.AccessDenied`
2. **Permission Model**: macOS uses `task_for_pid()` which has strict security requirements
3. **Error Propagation**: Single AccessDenied exception would crash entire collector
4. **NAS Dependencies**: Hard dependencies on NAS mounts that weren't available

## Solution Implemented

### 1. Network Tracker Robustness (`collectors/network_tracker.py`)

#### Platform Detection
```python
self.is_macos = platform.system() == 'Darwin'
if self.is_macos:
    self.logger.warning(
        "Running on macOS: psutil.net_connections() requires root. Using per-process enumeration fallback."
    )
```

#### Automatic Fallback Method
Implemented `_collect_via_process_iteration()` which:
- Iterates through accessible processes instead of system-wide connections
- Catches `AccessDenied` per-process and continues
- Caches failed PIDs to avoid repeated permission errors
- Returns only connections from processes the user owns

#### Error Handling Strategy
- Catches `psutil.AccessDenied` specifically
- Automatically switches to fallback on macOS or after 3 failed attempts  
- Maintains error counter but doesn't crash on expected permission errors
- Logs at appropriate levels (warning vs error)

### 2. NAS Availability Handling

#### Logger (`utils/logger.py`)
```python
try:
    self.nas_log_dir.mkdir(parents=True, exist_ok=True)
    self.nas_available = True
except (PermissionError, FileNotFoundError, OSError):
    self.nas_available = False
```

#### Database (`utils/db_v2.py`)
```python
if not getattr(self, 'nas_available', False):
    logger.debug("NAS backup unavailable")
    return False
```

#### Main Collector (`edr_collector_v2.py`)
- Warns user if NAS unavailable but continues with local storage
- Network collection errors marked as non-fatal

### 3. Key Improvements

**Graceful Degradation**: System continues operating with reduced functionality rather than crashing

**Platform Awareness**: Detects macOS and adjusts behavior accordingly

**Failed PID Caching**: Avoids repeatedly attempting to access PIDs that consistently fail

**Proper Exception Hierarchy**: Treats `psutil.AccessDenied` separately from unexpected errors

## Testing Results

### Stability Test
- ✅ Collector started successfully
- ✅ Ran continuously for 60+ seconds without crashes
- ✅ Network events collected: 167 events in 2 minutes
- ✅ Process monitoring operational
- ✅ File monitoring operational

### Log Analysis
```
WARNING - Running on macOS: psutil.net_connections() requires root. Using per-process enumeration fallback.
WARNING - Network collection AccessDenied (attempt 1): (pid=32012). Switching to per-process enumeration.
INFO - ✓ Network tracker initialized
INFO - ✓ Collection interval: 5s
INFO - ✓ EDR system is now ACTIVE
```

## Performance Impact

**Before Fix**: Collector crashed within 1 collection cycle (~5 seconds)

**After Fix**: Collector runs continuously, stable operation confirmed

**Network Collection**: Successfully collecting connections from user-owned processes without system-wide enumeration

## Known Limitations

1. **Reduced Visibility**: Only sees network connections for processes owned by current user
2. **No System Process Monitoring**: Cannot monitor connections from system processes or other users
3. **NAS Features Disabled**: When NAS unavailable, no remote backups or log sync

## Recommendations

### For Full Network Visibility (Optional)
To enable system-wide network connection monitoring on macOS:

1. **Run as root** (not recommended for security):
   ```bash
   sudo ~/Security/hybrid-edr/start_edr.sh
   ```

2. **Use macOS native tools** (alternative approach):
   - Shell out to `lsof -i -n -P`
   - Parse `netstat -an` output
   - Requires subprocess overhead but no permission issues

3. **Deploy on Linux** (preferred for production):
   - No permission restrictions on `/proc` filesystem
   - Better visibility and performance
   - Recommended for enterprise deployments

### For NAS Features
- Mount NAS volumes before starting collector
- Or accept local-only operation (sufficient for standalone monitoring)

## Files Modified

1. **collectors/network_tracker.py**
   - Added platform detection and fallback method
   - Implemented per-process connection enumeration
   - Enhanced exception handling

2. **utils/logger.py**
   - Made NAS log directory creation non-fatal
   - Added `nas_available` flag

3. **utils/db_v2.py**
   - Made NAS backup path creation non-fatal
   - Added availability check to `backup_to_nas()`

4. **edr_collector_v2.py**
   - Added NAS unavailability warnings
   - Made network collection errors non-fatal

## Conclusion

The EDR collector is now stable on macOS with graceful degradation when:
- Running without root privileges
- NAS storage is unavailable
- Permission errors occur on specific processes

The system continues monitoring with available capabilities rather than failing completely, following the principle of **resilience over perfection**.

---

**Fix Date**: December 3, 2025  
**Issue**: EDR Collector MacOS Crashes  
**Status**: ✅ Resolved  
**Testing**: Confirmed stable for 60+ seconds with active data collection
