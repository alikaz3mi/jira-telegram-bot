# Field-Level Change Detection for Story Synchronization

## Overview

The story synchronization system now implements **field-level change detection** to optimize Google Sheets updates. Instead of updating all 49 columns for every issue that has been modified in Jira, the system now:

1. **Detects** which specific fields have changed
2. **Updates** only the cells that have actual changes
3. **Skips** updates entirely if no tracked fields changed

## Tracked Fields

The system monitors changes in these specific fields:

| Field | Column | Description |
|-------|--------|-------------|
| `implementation_start_date` | U (20) | When implementation started |
| `deadline` | V (21) | Story deadline/due date |
| `status` | G (6) | Story status (with preservation logic) |
| `times` (progress) | AD+ (29+) | Developer work hours (progress) |

## How It Works

### Before (Old Behavior)
```
Jira Query: updated >= "2024-12-20"
- Finds all issues modified in any way (comments, attachments, etc.)
- Updates ALL 49 columns for each matched issue
- Writes unnecessary data to Google Sheets
```

### After (New Behavior)
```
Jira Query: updated >= "2024-12-20"
- Finds all issues modified in Jira
- Compares existing sheet data with Jira data
- Only updates cells where tracked fields changed
- Skips update if no tracked fields changed
```

## Example Scenarios

### Scenario 1: Comment Added to Story
**Jira Change**: Someone added a comment  
**Old Behavior**: Updates all 49 columns in sheet  
**New Behavior**: ✅ No update (comment doesn't affect tracked fields)

### Scenario 2: Deadline Changed
**Jira Change**: Deadline changed from 2024-01-01 to 2024-02-01  
**Old Behavior**: Updates all 49 columns in sheet  
**New Behavior**: ✅ Updates only column V (deadline)

### Scenario 3: Work Logged
**Jira Change**: Developer logged 8 hours of work  
**Old Behavior**: Updates all 49 columns in sheet  
**New Behavior**: ✅ Updates only the developer's progress column (e.g., column AD)

### Scenario 4: Status + Deadline Changed
**Jira Change**: Status moved to "In Progress" AND deadline changed  
**Old Behavior**: Updates all 49 columns in sheet  
**New Behavior**: ✅ Updates only columns G (status) and V (deadline)

### Scenario 5: Protected Status
**Jira Change**: Status changed in Jira, but sheet has protected status (۱, ۲, ۳, ۴, ۹, ۱۰)  
**Old Behavior**: Updates all 49 columns, preserves status  
**New Behavior**: ✅ No update (status preserved, no other changes)

## Benefits

### 1. Performance
- **Fewer API calls** to Google Sheets
- **Faster sync** operations
- **Reduced quota usage**

### 2. Data Integrity
- **Preserves manual edits** in non-tracked columns
- **Prevents race conditions** on unrelated fields
- **Respects status preservation** rules

### 3. Clarity
- **Debug logs** show exactly which fields changed
- **Visible reasoning** for each update
- **Easier troubleshooting**

## Implementation Details

### Key Methods

#### `_filter_rows_with_field_changes()`
Compares existing rows with updated rows to identify actual changes in tracked fields.

```python
def _filter_rows_with_field_changes(
    self,
    existing_rows: List[SynthPMFeatureEntity],
    update_rows: List[SynthPMFeatureEntity],
) -> List[SynthPMFeatureEntity]:
    """Filter update rows to only those with changes in tracked fields."""
```

#### `_update_changed_cells()`
Updates only the specific cells that have changed, using targeted range updates.

```python
async def _update_changed_cells(
    self,
    mapping: SheetBoardMapping,
    existing_rows: List[SynthPMFeatureEntity],
    changed_rows: List[SynthPMFeatureEntity],
) -> bool:
    """Update only the cells that have changed."""
```

### Column Mapping

The system uses fixed column indices for tracked fields:

```python
STATUS_COL = 6                # Column G
IMPLEMENTATION_START_COL = 20 # Column U
DEADLINE_COL = 21             # Column V
DEVELOPER_COLS_START = 29     # Column AD onwards
```

### Debug Logging

The system logs detailed information about changes:

```
[INFO] Incremental sync: 0 new, 5 updates (before filtering)
[DEBUG] MYPROJECT-123: deadline changed from 2024-01-01 to 2024-02-01
[DEBUG] MYPROJECT-456: progress (times) changed
[INFO] After field-level filtering: 2 rows have actual changes
[INFO] Updating 3 cells
```

## Testing

New test added to verify field-level change detection:

```python
async def test_field_level_change_detection_updates_only_changed_fields(self):
    """Test that only fields with changes are updated."""
```

This test verifies:
- ✅ Changes in deadline are detected
- ✅ Changes in progress are detected
- ✅ Unchanged fields are not updated
- ✅ Only specific cells are written to sheets

## Configuration

No configuration changes needed. The feature is automatically enabled for all incremental syncs (when `days_back` is specified).

### Full Sync vs Incremental Sync

- **Full Sync** (`days_back=None`): Overwrites entire sheet with all data
- **Incremental Sync** (`days_back=N`): Uses field-level change detection

## Migration Notes

### Backward Compatibility
✅ Fully backward compatible - no breaking changes

### Old Behavior
The old `_merge_data()` method is still available but no longer used in incremental sync flow.

### API Changes
- `_incremental_sync()` - Updated to use field-level detection
- New methods: `_filter_rows_with_field_changes()`, `_update_changed_cells()`, `_column_index_to_letter()`

## Future Enhancements

Potential improvements for future versions:

1. **Configurable tracked fields**: Allow users to specify which fields to track
2. **Change history**: Log what changed and when
3. **Batch updates**: Group cell updates into batch requests for better performance
4. **Field-level JQL**: Use Jira's changelog API to filter at query level
5. **Additional tracked fields**: Add more fields like priority, sprint, etc.

## References

- [Story Synchronization README](../story-synchronization/README.md)
- [Clean Architecture Patterns](../../infrastructure/architecture/README.md)
- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
