# Story Synchronization Configuration Guide

## Overview

The Story Synchronization feature is configured through the `story_sync_config.json` file, which defines mappings between Jira boards and Google Sheets.

## Configuration File Location

```
config/story_sync_config.json
```

## Configuration Schema

### SheetBoardMapping

Each mapping defines the relationship between a Jira board and a Google Sheet:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `spreadsheet_id` | string | Yes | - | Google Sheets spreadsheet ID (found in the URL) |
| `sheet_name` | string | Yes | - | Name of the specific sheet/tab within the spreadsheet |
| `board_key` | string | Yes | - | Jira board/project key (e.g., "PARSCHAT") |
| `gid` | integer | Yes | - | Google Sheet tab GID (numeric identifier) |
| `data_range` | string | No | `"A2:AW"` | Column range for sync operations |

### Data Range Format

The `data_range` field specifies the columns to read/write during sync operations:

- **Format**: `START_CELL:END_COLUMN`
  - Example: `"A2:AW"` means:
    - Start at column A, row 2 (row 1 contains headers)
    - End at column AW (column 49)

- **Column Range**: Based on your sheet structure
  - Standard range: `A2:AW` (49 columns total)
  - Columns A-AC: Fixed fields (29 columns)
  - Columns AD-AU: Dynamic developer columns (18 columns)
  - Columns AV-AW: Issue keys (2 columns)

## Example Configuration

```json
{
  "mappings": [
    {
      "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
      "sheet_name": "ParsChat Features",
      "board_key": "PARSCHAT",
      "gid": 1054397609,
      "data_range": "A2:AW"
    }
  ]
}
```

## Multiple Board Configuration

You can configure multiple board-to-sheet mappings:

```json
{
  "mappings": [
    {
      "spreadsheet_id": "...",
      "sheet_name": "Project A Features",
      "board_key": "PROJA",
      "gid": 123456,
      "data_range": "A2:AW"
    },
    {
      "spreadsheet_id": "...",
      "sheet_name": "Project B Features",
      "board_key": "PROJB",
      "gid": 789012,
      "data_range": "A2:AW"
    }
  ]
}
```

## Customizing the Data Range

### When to Customize

Customize `data_range` if you:
- Add or remove columns from your sheet
- Want to sync only specific columns
- Have a different sheet structure

### How to Calculate Your Range

1. **Count your columns**:
   - Fixed fields: Count columns A through last fixed column
   - Developer columns: Count how many developers you track
   - System columns: Typically 2 (jira_issue_key, developer_board_issue_key)

2. **Determine end column**:
   - Column 1 = A, Column 2 = B, ..., Column 26 = Z
   - Column 27 = AA, Column 28 = AB, ..., Column 49 = AW
   - Use an online column calculator if needed

3. **Update configuration**:
   ```json
   "data_range": "A2:YOUR_END_COLUMN"
   ```

## How the Range is Used

The system uses the configured range in three ways:

1. **Full Sync** (`A2:AW`): 
   - Clears and rewrites all data
   - Uses range with row number: `{sheet_name}!A2:AW`

2. **Incremental Update** (`A2:AW`):
   - Updates existing rows
   - Uses range with row number: `{sheet_name}!A2:AW`

3. **Append New Rows** (`A:AW`):
   - Adds new rows at the end
   - Uses column-only range: `{sheet_name}!A:AW`

## Entity Definition

The configuration is defined in:
```
jira_telegram_bot/entities/story_synchronization/story_sync_config.py
```

```python
class SheetBoardMapping(BaseModel):
    """Entity representing the mapping between a Google Sheet and a Jira board."""

    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(description="Name of the specific sheet/tab")
    board_key: str = Field(description="Jira board/project key")
    gid: int = Field(description="Google Sheet tab GID")
    data_range: str = Field(
        default="A2:AW",
        description="Data range for sync operations (e.g., 'A2:AW')",
    )
```

## Validation

The system validates that:
- No duplicate `board_key` values exist in mappings
- All required fields are present
- `data_range` is properly formatted (if provided)

## Loading Configuration

Configuration is loaded via dependency injection in:
```
jira_telegram_bot/config_dependency_injection.py
```

The loader:
1. Reads `config/story_sync_config.json`
2. Validates the schema
3. Creates `StorySyncConfig` entity
4. Returns validated configuration

## Troubleshooting

### Issue: Data truncated in Google Sheets

**Cause**: `data_range` end column is too small

**Solution**: 
1. Count your actual columns in the sheet
2. Update `data_range` to include all columns
3. Restart the sync process

### Issue: Sync fails with "range not found"

**Cause**: Invalid `data_range` format or column reference

**Solution**:
1. Verify range format: `START:END` (e.g., `A2:AW`)
2. Ensure end column exists in your sheet
3. Check for typos in column letters

### Issue: Headers not appearing

**Cause**: Range starts at row 1 instead of row 2

**Solution**:
- Use `A2:AW` (not `A1:AW`) to preserve headers in row 1

## Related Documentation

- [README.md](./README.md) - Feature overview and architecture
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Implementation details
- [Sheet Structure](./README.md#4-google-sheet-structure) - Column definitions
