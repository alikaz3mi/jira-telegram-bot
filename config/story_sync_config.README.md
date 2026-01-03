# Story Sync Configuration

## Date Filtering

You can filter tasks by their creation date using the `creation_date_filter` field in the `sync_settings` section.

### Configuration Field

- **`creation_date_filter`** (optional): Filter tasks created on or after this date (YYYY-MM-DD format)

### Behavior

The filter applies to the `creation_date` (تاریخ ایجاد) field in your Google Sheet.

A task will be **included** if:
- Its `creation_date` is on or after the specified filter date
- It has no `creation_date` set (backward compatibility - tasks without creation dates are always included)

A task will be **excluded** if:
- Its `creation_date` is before the specified filter date

### Why Use creation_date Filter Instead of Date Ranges?

**Advantages**:
1. **Tasks never disappear**: Once a task is created and synced, it stays in scope forever
2. **Free date updates**: You can freely update/remove `implementation_start_date` and `deadline` without losing the task
3. **Sprint flexibility**: Tasks can have their sprints removed without being filtered out
4. **Simpler logic**: Single filter date instead of complex range logic
5. **More intuitive**: "Show me tasks created since X" vs "Show me tasks with deadlines between X and Y"

**Use Cases**:
- Start syncing from a specific date forward: "Sync all tasks created since project kickoff"
- Ignore old/archived tasks: "Only sync tasks created this year"
- Gradual rollout: "Start with tasks created after migration date"

### Examples

#### Example 1: Filter tasks created from November 10, 2025 onwards
```json
"sync_settings": {
  "status_trigger_value": "۲",
  "sync_interval_minutes": 15,
  "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی",
  "creation_date_filter": "2025-11-10",
  "sprint_filter": null,
  "version_filter": null
}
```

This will include:
- All tasks with `creation_date` >= 2025-11-10
- All tasks without a `creation_date` (backward compatibility)

This will exclude:
- Tasks with `creation_date` < 2025-11-10

#### Example 2: No filtering (default - sync all tasks)
```json
"sync_settings": {
  "status_trigger_value": "۲",
  "sync_interval_minutes": 15,
  "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی",
  "creation_date_filter": null,
  "sprint_filter": null,
  "version_filter": null
}
```

### Migration from Old Date Filters

If you were using `date_filter_start` and `date_filter_end`, replace them with `creation_date_filter`:

**Before**:
```json
"date_filter_start": "2025-11-10",
"date_filter_end": null
```

**After**:
```json
"creation_date_filter": "2025-11-10"
```

### Notes

- Field is optional and defaults to `null` (no filtering)
- Date format must be `YYYY-MM-DD` (e.g., "2025-12-25")
- Tasks without `creation_date` are always included for backward compatibility
- The filter is applied when fetching features from Google Sheets
- This filter works independently from `sprint_filter` and `version_filter`

### Google Sheet Column

Make sure your Google Sheet has a "تاریخ ایجاد" (Creation Date) column that is properly mapped in the column headers.

Supported column names:
- `تاریخ ایجاد` (Persian)
- `Creation Date` (English)
