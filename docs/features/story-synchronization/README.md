# Story Synchronization Feature

## Overview

This feature automatically syncs Jira story data to Google Sheets, tracking progress hours, status updates, and worklog information for comprehensive project management.

## Features

- **Automatic Worklog Tracking**: Syncs time logged (Progress (h)) from Jira worklogs
- **Status Synchronization**: Maps Jira workflow statuses to Persian Google Sheet statuses
- **Two Sync Modes**:
  - Manual sync: One-time sync of all or specific boards
  - Scheduled sync: Continuous sync at regular intervals
- **Comprehensive Data**: Tracks:
  - Task details (title, epic, priority, status)
  - Time tracking (ETA, Total, Progress hours)
  - Department breakdowns (AI, Backend, Frontend, DevOps, UI/UX)
  - Individual developer hours
  - Important dates (created, implementation start, deadline, delivery)
  - Sprint information
  - PM board and Developer board issue keys
- **Incremental Updates**: Only updates changed stories to minimize API usage
- **Hyperlinked Issue Keys**: Direct links to both PM and Developer board issues

## Architecture

### Components

1. **Entities**
   - `StorySheetRow`: Represents a single row in the Google Sheet
   - `StorySyncConfig`: Configuration for board-to-sheet mappings
   - `SheetBoardMapping`: Individual mapping between a sheet and a board

2. **Use Cases**
   - `FetchStoryDataUseCase`: Fetches story data from Jira with worklog aggregation
   - `SyncStoryToSheetsUseCase`: Syncs data to Google Sheets

3. **Script**
   - `scripts/sync_stories.py`: CLI tool for running sync operations

## Setup

### 1. Google Sheets API Setup

1. Enable Google Sheets API in Google Cloud Console
2. Create OAuth 2.0 credentials
3. Download credentials JSON file
4. Set environment variables:

```bash
export GOOGLE_SHEETS_TOKEN_PATH=/path/to/token.json
```

### 2. Configure Board-to-Sheet Mappings

Edit `config/story_sync_config.json`:

```json
{
  "mappings": [
    {
      "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
      "sheet_name": "ParsChat Features",
      "board_key": "PARSCHAT",
      "gid": 1054397609
    }
  ]
}
```

### 3. Configure User Departments

Ensure `user_config.json` includes department information for worklog attribution:

```json
{
  "jira_username": "google_sheet_name": "کاظمی",
  "department": "Backend"
}
```

### 4. Google Sheet Structure

The sheet must have these columns (in order):

| Column | Persian Name | Description |
|--------|--------------|-------------|
| A | ردیف | Row number |
| B | وظیفه | Task title |
| C | Epic | Epic name |
| D | ضرورت | Necessity level |
| E | ریلیز | Release version |
| F | Departments | Components |
| G | وضعیت | Status (mapped from Jira) |
| H | اولویت | Priority |
| I | Department Deps | Department dependencies |
| J | ریلیز اصلی | Main release |
| K | ETA(h) | Estimated hours |
| L | Total (h) | Total hours |
| M | Progress (h) | **Synced from worklogs** |
| N | افراد درگیر | Involved people |
| O | AI | AI team hours |
| P | Backend | Backend team hours |
| Q | Front-end | Frontend team hours |
| R | DevOps | DevOps team hours |
| S | UI / UX | UI/UX team hours |
| T | تاریخ ایجاد | Created date |
| U | تاریخ شروع پیاده سازی | Implementation start |
| V | ددلاین | Deadline |
| W | اسپرینت | Sprint |
| X | وابستگی ها | Dependencies |
| Y | زمان تحویل اولیه | Initial delivery time |
| Z | توضیحات | Description |
| AA | معیارهای پذیرش | Acceptance criteria |
| AB | تست ها | Tests |
| AC | علل تغییر یا توقف | Change reasons |
| AD-AU | Individual developers | کاظمی، موسوی، مرادی، etc. |
| AV | jira_issue_key | PM board issue key |
| AW | developer_board_issue_key | Developer board issue key |

## Usage

### Manual Sync

#### Sync All Boards (Full)
```bash
python scripts/sync_stories.py sync --full
```

#### Sync Specific Boards (Last 30 Days)
```bash
python scripts/sync_stories.py sync --boards PARSCHAT
```

#### Sync All Boards (Last 30 Days - Default)
```bash
python scripts/sync_stories.py sync
```

#### Sync with Custom Days Back
```bash
python scripts/sync_stories.py sync --days-back 14
```

### Scheduled Sync

#### Run Every 5 Minutes (Default - Last 7 Days)
```bash
python scripts/sync_stories.py scheduled
```

#### Run Every 10 Minutes (Last 14 Days)
```bash
python scripts/sync_stories.py scheduled --interval 10 --days-back-scheduled 14
```

### Test Connections

```bash
python scripts/sync_stories.py test
```

## Data Mapping

### Key Updates

#### Progress (h) - Column M
- **Source**: Aggregated from all worklogs on the story
- **Calculation**: Sum of `timeSpentSeconds` / 3600 from all worklog entries
- **Updates**: Every sync updates this field based on latest worklog data

#### وضعیت (Status) - Column G
- **Source**: `issue.fields.status.name`
- **Mapping**: Jira status → Persian workflow status (via `JIRA_TO_GOOGLE_SHEET_STATUS`)
- **Updates**: Reflects current status in Jira

### Worklog Attribution

The system aggregates worklog data by:
1. Fetching all worklogs for the story
2. Summing hours for overall Progress (h)
3. Attributing hours to departments based on user configuration
4. Tracking individual developer hours in separate columns

### Department Hours Calculation

Department hours are calculated based on:
- User's department from `user_config.json`
- Time logged in worklogs
- Department mapping:
  - AI → AI hours (Column O)
  - Backend → Backend hours (Column P)
  - Frontend/Front-end → Front-end hours (Column Q)
  - DevOps → DevOps hours (Column R)
  - UI/UX → UI / UX hours (Column S)

### Individual Developer Hours

Each developer has a dedicated column (AD-AU) showing their total logged hours on the story.

### Issue Key Tracking

- **jira_issue_key** (Column AV): PM board issue (e.g., PCD-973) - linked from developer board story
- **developer_board_issue_key** (Column AW): Developer board issue (e.g., PARSCHAT-4382) - primary key for sync

## Technical Details

### Sync Logic

#### Full Sync
1. Clear all existing data (preserving headers)
2. Fetch all stories from Jira
3. Aggregate worklog data
4. Write all data to sheet

#### Incremental Sync
1. Fetch stories updated in the last N days
2. Aggregate latest worklog data
3. Identify new vs. existing stories (by developer_board_issue_key)
4. Update existing rows with new Progress (h) and status
5. Append new rows

### Worklog Data Extraction

```python
# For each story:
1. Fetch issue with worklog expansion
2. Iterate through all worklogs
3. Sum timeSpentSeconds → Progress (h)
4. Track author and department
5. Build individual hours mapping
```

### Performance Considerations

- Uses JQL filtering for efficient queries
- Worklog expansion minimizes API calls
- Batch writes to Google Sheets
- Incremental sync reduces data transfer
- Retry logic for Google Sheets quota limits

### Error Handling

- Graceful degradation on missing worklog data
- Logging for all operations
- Retry logic for API failures (up to 5 retries with exponential backoff)
- Validation of configuration

## Cron Job Setup

To run as a scheduled cron job:

```bash
# Every 5 minutes during work hours (9 AM - 6 PM)
*/5 9-18 * * 1-5 cd /path/to/jira-telegram-bot && python scripts/sync_stories.py sync --days-back 7

# Or use scheduled mode (runs continuously)
# Add to systemd service or supervisor
python scripts/sync_stories.py scheduled --interval 5 --days-back-scheduled 7
```

## Integration with Existing System

Clean Architecture implementation:

```
jira_telegram_bot/
├── entities/
│   └── story_synchronization/
│       ├── __init__.py
│       ├── story_sheet_row.py
│       └── story_sync_config.py
├── use_cases/
│   └── story_synchronization/
│       ├── __init__.py
│       ├── fetch_story_data_use_case.py
│       └── sync_story_to_sheets_use_case.py
├── config_dependency_injection.py (DI registration)
└── scripts/
    └── sync_stories.py
```

## Environment Variables

```bash
# Google Sheets
GOOGLE_SHEETS_TOKEN_PATH=/path/to/token.json

# Jira
JIRA_DOMAIN=your-jira-instance.atlassian.net
JIRA_USERNAME=your-username
JIRA_API_TOKEN=your-api-token

# Optional
CONFIG_DIR=./config
DATA_DIR=./data
```

## Troubleshooting

### Missing Worklog Data

If Progress (h) shows 0:
1. Verify worklogs exist in Jira for the story
2. Check Jira API permissions for worklog access
3. Review logs for worklog fetch errors

### User Department Not Found

If department hours aren't attributed:
1. Ensure user exists in `user_config.json`
2. Verify `department` field is set correctly
3. Check department name matches mapping (AI, Backend, Frontend, DevOps, UI/UX)

### Google Sheets Quota Exceeded

The system includes automatic retry logic:
- Waits 60 seconds on first retry
- Increases wait time on subsequent retries
- Logs quota errors for monitoring

To reduce quota usage:
- Use incremental sync (default)
- Increase sync interval for scheduled mode
- Reduce --days-back parameter

## Examples

### Example 1: Daily Full Sync
```bash
# Full sync once per day at 8 AM
0 8 * * * python /path/to/scripts/sync_stories.py sync --full
```

### Example 2: Incremental Sync Every 15 Minutes
```bash
# Sync last 7 days of changes every 15 minutes
*/15 * * * * python /path/to/scripts/sync_stories.py sync --days-back 7
```

### Example 3: Continuous Scheduled Sync
```bash
# Run as background service
python scripts/sync_stories.py scheduled --interval 10 --days-back-scheduled 14
```

## Future Enhancements

- [ ] Real-time sync via Jira webhooks
- [ ] Custom field support
- [ ] Filtering by labels or sprints
- [ ] Dashboard generation
- [ ] Email notifications on sync completion
- [ ] Worklog comment inclusion
- [ ] Historical worklog tracking

## Contributing

When modifying this feature:
1. Follow Clean Architecture principles
2. Add tests for new functionality
3. Update this documentation
4. Maintain backward compatibility
5. Follow Copilot Custom Instructions

## License

Same as parent project.
