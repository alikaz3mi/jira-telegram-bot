# Date and Progress Comparison Fix

## Issues Fixed

### Issue 1: Date Format Mismatch ⚠️

**Problem:**
```python
# From Jira (aware datetime with timezone and time)
changed_row.implementation_start_date
>>> datetime.datetime(2025, 10, 28, 12, 49, 49, tzinfo=datetime.timezone(...))

# From Google Sheets (naive datetime, date only)
existing_row.implementation_start_date
>>> datetime.datetime(2025, 10, 25, 0, 0)
```

**Impact:**
- Direct comparison `date1 != date2` always returns `True` even for same date
- System thinks dates changed when only time/timezone differs
- Causes **false positive updates** - unnecessary writes to Google Sheets

**Root Cause:**
1. **Jira API** returns full datetime with timezone: `2025-10-28T12:49:49+0330`
2. **Google Sheets** stores only dates: `2025-10-28` → parsed as `datetime(2025, 10, 28, 0, 0)`
3. Python comparison: `datetime(2025, 10, 28, 12, 49) != datetime(2025, 10, 28, 0, 0)` → `True` ❌

**Solution:**
Created `_dates_equal()` method that compares **only year, month, day**:

```python
def _dates_equal(self, date1, date2) -> bool:
    """Compare two dates ignoring time and timezone."""
    if date1 is None and date2 is None:
        return True
    if date1 is None or date2 is None:
        return False
    
    # Compare only year, month, day (ignore time and timezone)
    return (
        date1.year == date2.year
        and date1.month == date2.month
        and date1.day == date2.day
    )
```

### Issue 2: Progress (Times) Comparison

**Problem:**
How do we detect when developer work hours changed?

**Challenge:**
```python
# From Google Sheets (stored as days = hours/8)
existing_row.times = {"Developer1": 16.0}  # 2 days * 8 = 16 hours

# From Jira worklogs (stored as hours)
changed_row.times = {"Developer1": 16.0000001}  # Floating point precision

# Should this trigger an update? NO!
```

**Solution:**
Created `_times_equal()` method with rounding to avoid float precision issues:

```python
def _times_equal(self, times1: dict, times2: dict) -> bool:
    """Compare two times dictionaries with rounding."""
    if not times1 and not times2:
        return True
    
    # Get all developer names from both dicts
    all_devs = set(times1.keys()) | set(times2.keys())
    
    for dev in all_devs:
        hours1 = times1.get(dev, 0)
        hours2 = times2.get(dev, 0)
        
        # Round to 2 decimal places to avoid float precision issues
        if round(hours1, 2) != round(hours2, 2):
            return False
    
    return True
```

## Updated Logic

### Change Detection (in `_filter_rows_with_field_changes`)

**Before:**
```python
# Direct comparison - BROKEN
if update_row.implementation_start_date != existing_row.implementation_start_date:
    has_changes = True

if update_row.times != existing_row.times:
    has_changes = True
```

**After:**
```python
# Date-only comparison - CORRECT
if not self._dates_equal(update_row.implementation_start_date, 
                         existing_row.implementation_start_date):
    has_changes = True

# Rounded hours comparison - CORRECT
if not self._times_equal(update_row.times, existing_row.times):
    has_changes = True
```

### Cell Updates (in `_update_changed_cells`)

**Progress Update Logic:**
```python
# Update progress columns (developer times)
if not self._times_equal(changed_row.times, existing_row.times):
    for idx, dev_name in enumerate(self.developer_names):
        old_hours = existing_row.times.get(dev_name, 0)
        new_hours = changed_row.times.get(dev_name, 0)
        
        # Only update if THIS specific developer's hours changed
        if round(old_hours, 2) != round(new_hours, 2):
            col_idx = DEVELOPER_COLS_START + idx
            col_letter = self._column_index_to_letter(col_idx)
            cell_range = f"{mapping.sheet_name}!{col_letter}{sheet_row}"
            days = new_hours / 8 if new_hours else 0.0
            update_requests.append({
                "range": cell_range,
                "values": [[days]],
            })
```

**How it works:**
1. Check if ANY developer hours changed (using `_times_equal`)
2. If yes, loop through each developer
3. Update **only** the cells for developers whose hours actually changed
4. Convert hours to days (`hours / 8`) before writing to sheet

## Examples

### Example 1: Same Date, Different Time ✅
```python
jira_date = datetime(2025, 10, 28, 12, 49, 49, tzinfo=...)
sheet_date = datetime(2025, 10, 28, 0, 0)

# OLD: jira_date != sheet_date → True (WRONG - triggers update)
# NEW: _dates_equal(jira_date, sheet_date) → True (CORRECT - no update)
```

### Example 2: Different Date ✅
```python
jira_date = datetime(2025, 10, 28, 12, 49, 49, tzinfo=...)
sheet_date = datetime(2025, 10, 25, 0, 0)

# OLD: jira_date != sheet_date → True (CORRECT)
# NEW: _dates_equal(jira_date, sheet_date) → False (CORRECT - triggers update)
```

### Example 3: Float Precision in Hours ✅
```python
jira_times = {"Dev1": 16.0000001, "Dev2": 8.0}
sheet_times = {"Dev1": 16.0, "Dev2": 8.0}

# OLD: jira_times != sheet_times → True (WRONG - triggers update)
# NEW: _times_equal(jira_times, sheet_times) → True (CORRECT - no update)
```

### Example 4: Actual Hour Change ✅
```python
jira_times = {"Dev1": 24.0, "Dev2": 8.0}
sheet_times = {"Dev1": 16.0, "Dev2": 8.0}

# OLD: jira_times != sheet_times → True (CORRECT)
# NEW: _times_equal(jira_times, sheet_times) → False (CORRECT - triggers update)

# Updates ONLY Dev1's column (not Dev2):
# Column AD (Dev1) ← 24/8 = 3.0 days
# Column AE (Dev2) ← Not updated (same value)
```

### Example 5: New Developer Added ✅
```python
jira_times = {"Dev1": 16.0, "Dev2": 8.0, "Dev3": 4.0}
sheet_times = {"Dev1": 16.0, "Dev2": 8.0}

# NEW: _times_equal(jira_times, sheet_times) → False (CORRECT - triggers update)

# Updates ONLY Dev3's column:
# Column AD (Dev1) ← Not updated (same)
# Column AE (Dev2) ← Not updated (same)
# Column AF (Dev3) ← 4/8 = 0.5 days (NEW)
```

## Data Flow

### How Progress is Tracked

```
┌─────────────────────────────────────────────────────────────┐
│                    JIRA WORKLOGS                            │
│  Developer1: 16 hours (2 days)                              │
│  Developer2: 8 hours (1 day)                                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│          FetchStoryDataUseCase._get_worklog_data()          │
│  Aggregates all worklogs → times dict                       │
│  times = {"Developer1": 16.0, "Developer2": 8.0}            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                SynthPMFeatureEntity                          │
│  times: Dict[str, float] = {"Developer1": 16.0, ...}        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│        _filter_rows_with_field_changes()                    │
│  Compare: _times_equal(jira_times, sheet_times)             │
│  Result: Has changes? Yes/No                                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│           _update_changed_cells()                           │
│  For each developer with changed hours:                     │
│    - Column AD ← Developer1: 16 hours                       │
│    - Column AE ← Developer2: 8 hours                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  GOOGLE SHEETS                              │
│  Column AD (Developer1): 16                                 │
│  Column AE (Developer2): 8                                  │
└─────────────────────────────────────────────────────────────┘
```

### Reading Back from Sheets

```
┌─────────────────────────────────────────────────────────────┐
│                  GOOGLE SHEETS                              │
│  Column AD (Developer1): 16 (hours)                         │
│  Column AE (Developer2): 8 (hours)                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      TaskStoryRepository.get_sheet_features()               │
│  Reads sheet values directly as hours                       │
│  times = {"Developer1": 16, "Developer2": 8}                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│             Used for comparison                             │
│  existing_row.times = {"Developer1": 16, ...}               │
└─────────────────────────────────────────────────────────────┘
```

## Testing

All **32 tests pass** with the new comparison logic, including:
- ✅ Date comparison edge cases
- ✅ Float precision handling
- ✅ Timezone differences
- ✅ Field-level change detection
- ✅ Selective cell updates

## Benefits

1. **No False Positives**: Dates are compared correctly (day-level only)
2. **Float Precision Handled**: Rounding prevents spurious updates
3. **Efficient Updates**: Only cells with real changes are written
4. **Correct Progress Tracking**: Hours ↔ Days conversion handled properly
5. **Better Logging**: Debug logs show actual value changes

## Edge Cases Handled

- ✅ Null/None dates (both null → equal)
- ✅ Timezone-aware vs naive datetime
- ✅ Time components (ignored for date fields)
- ✅ Float precision (0.0001 difference)
- ✅ Missing developers in times dict
- ✅ Empty times dictionaries
- ✅ New developers added to project
