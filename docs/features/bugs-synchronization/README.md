# Bug/Improvement Google Sheets Sync Feature

## Overview

This feature automatically syncs Jira bugs and improvements to Google Sheets, providing comprehensive tracking and reporting capabilities.

## Features

- **Automatic Sync**: Sync bugs and improvements from Jira to Google Sheets
- **Two Sync Modes**:
  - Manual sync: One-time sync of all or specific boards
  - Scheduled sync: Continuous sync at regular intervals
- **Comprehensive Data**: Tracks all relevant information including:
  - Task details (title, description, priority, status)
  - Epic and linked story information
  - Departments (components)
  - Time tracking (total hours, involved people)
  - Important dates (created, implementation start, deadline, delivery)
  - Sprint information
- **Subtask Support**: Aggregates time and assignees from subtasks
- **Hyperlinked Issue Keys**: Direct links to Jira issues

## Architecture

### Components

1. **Entities**
   - `BugImprovementSheetRow`: Represents a single row in the Google Sheet
   - `BugImprovementSyncConfig`: Configuration for board-to-sheet mappings
   - `SheetBoardMapping`: Individual mapping between a sheet and a board

2. **Use Cases**
   - `FetchBugImprovementDataUseCase`: Fetches bug/improvement data from Jira
   - `SyncBugImprovementToSheetsUseCase`: Syncs data to Google Sheets

3. **Repository**
   - `GoogleSheetsRepository`: Handles all Google Sheets API operations

4. **Script**
   - `scripts/sync_bugs_improvements.py`: CLI tool for running sync operations

## Setup

### 1. Google Sheets API Setup

1. Enable Google Sheets API in Google Cloud Console
2. Create OAuth 2.0 credentials
3. Download credentials JSON file
4. Set environment variables:

```bash
export GOOGLE_SHEETS_TOKEN_PATH=config/token.json
```

### 2. Configure Board-to-Sheet Mappings

Edit `config/bug_improvement_sync_config.json`:

```json
{
  "mappings": [
    {
      "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
      "sheet_name": "Bugs - Project A",
      "board_key": "PROJA",
      "gid": 1945361091
    },
    {
      "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
      "sheet_name": "Bugs - Project B",
      "board_key": "PROJB",
      "gid": 1945361092
    }
  ]
}
```

### 3. Prepare Google Sheet

Create a sheet with these column headers (in Persian and English):

| ردیف | وظیفه | توضیحات | Epic | Story | اولویت | وضعیت | Departments | ریلیز | Total (h) | افراد درگیر | تاریخ ایجاد | تاریخ شروع پیاده سازی | ددلاین | اسپرینت | زمان تحویل اولیه | issue_key |

## Usage

### Manual Sync

#### Sync All Boards (Full)
```bash
python scripts/sync_bugs_improvements.py sync --full
```

#### Sync Specific Boards (Last 30 Days)
```bash
python scripts/sync_bugs_improvements.py sync --boards PROJ1 PROJ2
```

#### Sync All Boards (Last 30 Days)
```bash
python scripts/sync_bugs_improvements.py sync
```

### Scheduled Sync

#### Run Every 5 Minutes (Default - Last 7 Days)
```bash
python scripts/sync_bugs_improvements.py scheduled
```

#### Run Every 10 Minutes (Last 14 Days)
```bash
python scripts/sync_bugs_improvements.py scheduled --interval 10 --days-back 14
```

### Test Connections

```bash
python scripts/sync_bugs_improvements.py test
```

## Data Mapping

### Column Details

| Column | Source | Notes |
|--------|--------|-------|
| ردیف (Row Number) | Auto-generated | Sequential numbering |
| وظیفه (Task Title) | `issue.fields.summary` | Task summary |
| توضیحات (Description) | `issue.fields.description` | Task description |
| Epic | Epic name from epic link | Fetched from linked epic |
| Story | Linked story key | From issue links |
| اولویت (Priority) | `issue.fields.priority.name` | Task priority |
| وضعیت (Status) | `issue.fields.status.name` | Current status |
| Departments | `issue.fields.components` | Component names |
| ریلیز (Release) | `issue.fields.fixVersions[0].name` | Fix version |
| Total (h) | Aggregated from subtasks | Sum of time spent |
| افراد درگیر (Involved People) | Assignees from issue + subtasks | Unique list |
| تاریخ ایجاد (Created Date) | `issue.fields.created` | Creation timestamp |
| تاریخ شروع پیاده سازی (Implementation Start) | From changelog | When moved to In Progress |
| ددلاین (Deadline) | `issue.fields.duedate` | Due date |
| اسپرینت (Sprint) | Sprint name | Last sprint |
| زمان تحویل اولیه (Initial Delivery) | From changelog | When moved to Done |
| issue_key | `issue.key` | Hyperlinked to Jira |

### Subtask Handling

When a bug/improvement has subtasks:
- **Total Hours**: Sum of time spent on all subtasks
- **Involved People**: Union of assignees from parent issue and all subtasks

### Linked Story Detection

The system searches issue links for:
- Outward links to Story type issues
- Inward links from Story type issues

## Technical Details

### Sync Logic

#### Full Sync
1. Clear all existing data (preserving headers)
2. Fetch all bugs and improvements
3. Write all data to sheet

#### Incremental Sync
1. Fetch issues updated in the last N days
2. Identify new vs. existing issues
3. Update existing rows
4. Append new rows

### Performance Considerations

- Uses JQL filtering for efficient queries
- Caches Jira data to minimize API calls
- Batch writes to Google Sheets
- Supports pagination for large datasets

### Error Handling

- Graceful degradation on missing data
- Logging for all operations
- Retry logic for API failures
- Validation of configuration

## Integration with Existing System

This feature integrates seamlessly with the existing Clean Architecture:

```
jira_telegram_bot/
├── entities/
│   ├── bug_improvement_sheet_row.py
│   └── bug_improvement_sync_config.py
├── use_cases/
│   ├── fetch_bug_improvement_data_use_case.py
│   ├── sync_bug_improvement_to_sheets_use_case.py
│   └── interfaces/
│       └── google_sheets_repository_interface.py
├── adapters/
│   └── repositories/
│       └── google_sheets/
│           └── google_sheets_repository.py
└── settings/
    └── google_sheets_settings.py
```

## Environment Variables

```bash
# Google Sheets
GOOGLE_SHEETS_TOKEN_PATH=config/token.json

# Jira (existing)
JIRA_DOMAIN=your-jira-instance.atlassian.net
JIRA_USERNAME=your-username
JIRA_API_TOKEN=your-api-token

# Optional
CONFIG_DIR=./config
DATA_DIR=./data
```

## Troubleshooting

### Google Sheets Authentication Issues

If you see "No valid credentials found":
1. Ensure `GOOGLE_SHEETS_TOKEN_PATH` is set correctly
2. Verify the token file exists and is valid
3. Re-run OAuth flow if token expired

### Missing Data

- **Epic Name**: Ensure epic link custom field is configured
- **Linked Story**: Check issue links are properly set in Jira
- **Time Data**: Verify subtasks have time logged

### Performance Issues

- Reduce `--days-back` parameter
- Increase `--interval` for scheduled sync
- Optimize JQL queries in configuration

## Future Enhancements

- [ ] Support for custom fields
- [ ] Filtering by labels
- [ ] Multiple sheet tabs per board
- [ ] Real-time sync via webhooks
- [ ] Dashboard generation
- [ ] Email notifications on sync completion

## Contributing

When modifying this feature:
1. Follow Clean Architecture principles
2. Add tests for new functionality
3. Update this documentation
4. Maintain backward compatibility

## License

Same as parent project.
