# Multi-Project Jira Synchronization

This directory contains scripts to synchronize multiple Jira projects to the PostgreSQL database, with built-in duplicate prevention.

## Scripts

### 1. `sync_all_projects_last_month.py`
Simple script that syncs all configured projects for the last 30 days.

**Usage:**
```bash
python scripts/sync_all_projects_last_month.py
```

**Features:**
- Syncs all projects defined in `SYNC_PROJECT_KEYS` environment variable
- Fetches issues updated in the last 30 days
- Automatically prevents duplicates using database upsert mechanism
- Logs detailed progress for each project

### 2. `sync_projects_date_range.py`
Flexible script with command-line options for custom date ranges and project selection.

**Usage:**
```bash
# Sync all projects from last month (default)
python scripts/sync_projects_date_range.py

# Sync specific projects from last 7 days
python scripts/sync_projects_date_range.py --projects PROJ1 PROJ2 --days 7

# Sync all projects from a specific date
python scripts/sync_projects_date_range.py --since 2025-12-01

# Full sync (all issues, ignore date filter)
python scripts/sync_projects_date_range.py --full-sync

# Sync from last 90 days
python scripts/sync_projects_date_range.py --days 90
```

**Options:**
- `--projects`: Specific project keys to sync (space-separated)
- `--days`: Number of days to look back (default: 30)
- `--since`: Sync issues updated since this date (YYYY-MM-DD format)
- `--full-sync`: Perform full sync (all issues, ignoring date filters)

## Configuration

Projects are configured via environment variables in your `.env` file:

```env
# List of project keys to synchronize (comma-separated)
SYNC_PROJECT_KEYS=PROJECT1,PROJECT2,PROJECT3,PROJ4,MYPROJECT

# Sync interval in minutes (for scheduled sync)
SYNC_INTERVAL_MINUTES=10

# Whether to perform full sync or incremental
SYNC_FULL_SYNC=true
```

## How Duplicate Prevention Works

The synchronization uses PostgreSQL's **upsert** mechanism to prevent duplicates:

1. **Primary Key**: The `jira_tasks_enhanced` table uses `key` (issue key) as the primary key
2. **Merge Operation**: The repository uses `session.merge()` which:
   - **Inserts** new issues if they don't exist
   - **Updates** existing issues if they already exist
3. **Status History**: Status change history is replaced (DELETE + INSERT) to ensure accuracy

### Database Operations

```python
# In jira_report_repository.py
for issue in issues:
    task_model = self._convert_to_model(issue)
    session.merge(task_model)  # ← Automatic upsert!
    
    # Status history is replaced
    session.execute(
        text("DELETE FROM jira_status_history WHERE issue_key = :key"),
        {"key": issue.key}
    )
    # Then insert fresh history
```

This means you can **safely run the sync scripts multiple times** without creating duplicates!

## Typical Workflow

### Initial Setup
```bash
# 1. Configure your projects in .env
echo "SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3" >> .env

# 2. Run full sync for the first time
python scripts/sync_projects_date_range.py --full-sync

# 3. Verify in database
psql -d your_database -c "SELECT project, COUNT(*) FROM jira_tasks_enhanced GROUP BY project;"
```

### Regular Updates
```bash
# Sync last week's changes
python scripts/sync_all_projects_last_month.py

# Or with custom range
python scripts/sync_projects_date_range.py --days 7
```

### Adding New Projects
```bash
# 1. Add to .env
echo "SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3,NEWPROJECT" >> .env

# 2. Run full sync for new project only
python scripts/sync_projects_date_range.py --projects NEWPROJECT --full-sync

# 3. Future syncs will include it automatically
python scripts/sync_all_projects_last_month.py
```

## Logging

All sync operations log to:
- **Console**: Real-time progress with project-by-project details
- **Log files**: `logs.log.*` files in project root

Example output:
```
2026-01-05 10:30:00 - INFO - ================================================================================
2026-01-05 10:30:00 - INFO - Starting multi-project synchronization for last month
2026-01-05 10:30:00 - INFO - ================================================================================
2026-01-05 10:30:00 - INFO - Syncing 3 project(s) for issues updated since: 2025-12-05 10:30:00
2026-01-05 10:30:00 - INFO - --------------------------------------------------------------------------------
2026-01-05 10:30:00 - INFO - Processing project: PROJECT1
2026-01-05 10:30:05 - INFO - Found 45 updated issue(s) for PROJECT1, storing to database...
2026-01-05 10:30:08 - INFO - ✓ Successfully synced 45 issue(s) for PROJECT1
...
2026-01-05 10:35:00 - INFO - ================================================================================
2026-01-05 10:35:00 - INFO - Multi-project synchronization completed
2026-01-05 10:35:00 - INFO - Total issues synced: 132
2026-01-05 10:35:00 - INFO - Projects failed: 0
2026-01-05 10:35:00 - INFO - ================================================================================
```

## Troubleshooting

### No issues synced
- Check that project keys in `.env` match your Jira projects
- Verify date range covers when issues were last updated
- Check Jira API credentials

### Sync fails for specific project
- Check logs for detailed error message
- Verify project exists and you have access
- Try syncing just that project: `--projects PROJECTKEY`

### Performance issues
- Use date filtering instead of full sync
- Sync projects individually rather than all at once
- Consider running during off-peak hours

## Related Files

- `jira_telegram_bot/settings/jira_sync_settings.py` - Settings configuration
- `jira_telegram_bot/use_cases/sync_jira_issue_use_case.py` - Core sync logic
- `jira_telegram_bot/adapters/repositories/postgres/jira_report_repository.py` - Database operations
- `jira_telegram_bot/adapters/services/jira_data_service.py` - Jira API integration
