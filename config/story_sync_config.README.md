# Story Sync Configuration

## Date Filtering

You can filter tasks by their dates using the `date_filter_start` and `date_filter_end` fields in the `sync_settings` section.

### Configuration Fields

- **`date_filter_start`** (optional): Filter tasks with dates >= this date (YYYY-MM-DD format)
- **`date_filter_end`** (optional): Filter tasks with dates <= this date (YYYY-MM-DD format)

### Behavior

The filter applies to both:
- `implementation_start_date` (Target Start)
- `deadline` (Due Date)

A task will be **included** if:
- Either of its dates (implementation_start_date or deadline) falls within the specified range
- It has no dates set (tasks without dates are always included)

A task will be **excluded** if:
- Both dates are outside the specified range

### Examples

#### Example 1: Filter tasks for December 2025
```json
"sync_settings": {
  "status_trigger_value": "۲",
  "sync_interval_minutes": 1,
  "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی",
  "date_filter_start": "2025-12-01",
  "date_filter_end": "2025-12-31"
}
```

#### Example 2: Filter tasks starting from a specific date (no end date)
```json
"sync_settings": {
  "status_trigger_value": "۲",
  "sync_interval_minutes": 1,
  "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی",
  "date_filter_start": "2025-12-15",
  "date_filter_end": null
}
```

#### Example 3: No filtering (default)
```json
"sync_settings": {
  "status_trigger_value": "۲",
  "sync_interval_minutes": 1,
  "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی",
  "date_filter_start": null,
  "date_filter_end": null
}
```

### Notes

- Both fields are optional and default to `null` (no filtering)
- You can specify only `date_filter_start` or only `date_filter_end`
- Date format must be `YYYY-MM-DD` (e.g., "2025-12-25")
- If a task has no dates set, it will always be included regardless of the filter
- The filter is applied when fetching features from Google Sheets
