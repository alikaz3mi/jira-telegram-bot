# Actual Start/End Dates Implementation

## Overview

This implementation adds support for tracking **Actual Start Date** and **Actual End Date** for Jira issues. These fields are date pickers (without time) automatically populated by a Jira listener/automation, and the sync service reads these values into PostgreSQL.

## Custom Fields in Jira

Two date picker custom fields are used in Jira:
- **Actual Start Date**: `customfield_10702`
- **Actual End Date**: `customfield_10703`

**Important**: These fields are automatically set by Jira automation/listener rules. The sync service simply reads these values and stores them in PostgreSQL.

## Database Changes

### Migration 010
Adds two new columns to the `jira_tasks_enhanced` table:
- `actual_start_date` (TIMESTAMP)
- `actual_end_date` (TIMESTAMP)

### Running the Migration

```bash
python scripts/run_migration_010.py
```

## How It Works

### Jira Side (Automated by Jira Listener)
The Jira listener automatically sets:
- **Actual Start Date**: When issue moves to "In Progress" or first worklog is added
- **Actual End Date**: When issue moves to "Done"

### Sync Side (Our Application)
The sync service reads these pre-calculated values from Jira custom fields and stores them in PostgreSQL:
1. Fetches issues from Jira (includes custom fields)
2. Reads `customfield_10700` (actual_start_date)
3. Reads `customfield_10701` (actual_end_date)
4. Stores values in `jira_tasks_enhanced` table

## Code Changes

### 1. Entities Updated
- `jira_telegram_bot/entities/jira_report.py` - Added `actual_start_date` and `actual_end_date` fields
- `jira_telegram_bot/entities/task.py` - Added `actual_start_date` and `actual_end_date` fields

### 2. Repository Updates
- `jira_telegram_bot/adapters/repositories/jira/jira_server_repository.py`
  - Added `jira_actual_start_id` and `jira_actual_end_id` field IDs
  
- `jira_telegram_bot/adapters/repositories/postgres/jira_report_repository.py`
  - Updated `JiraTaskModel` to include new columns
  - Updated `_convert_to_model()` and `_convert_from_model()` methods

### 3. Service Updates
- `jira_telegram_bot/adapters/services/jira_data_service.py`
  - Updated `_convert_to_detailed_issue()` to read actual dates from Jira custom fields
  - No calculation logic needed (values come from Jira listener)

### 4. Dependency Injection
- `jira_telegram_bot/config_dependency_injection.py`
  - Added `CalculateActualDatesUseCase` to container (for one-time historical backfill if needed)

## One-Time Historical Backfill

**Note**: This is only needed if you want to backfill historical issues where the Jira listener hasn't set values yet.

### Backfill Use Case
- `jira_telegram_bot/use_cases/calculate_actual_dates_use_case.py`
  - Calculates actual dates from changelog/worklog history
  - Updates Jira custom fields for issues where they're empty
  - Should only be run once for historical data

### Backfill Script

**Warning**: This script queries Jira with changelog and worklog expansion, which can be slow for large projects.

```bash
# Modify the script to process one project at a time
python scripts/backfill_actual_dates.py
```

### Alternative: Let Sync Handle It
Instead of running a backfill, you can simply:
1. Run the migration to add database columns
2. Let the regular sync pick up values from Jira (for issues where the listener has already set them)
3. For old issues without values, they'll remain empty until the Jira listener triggers (if/when they're updated)

## Automatic Sync Integration

The sync service automatically reads actual dates from Jira for all issues:

1. **During Regular Sync** (`scripts/run_scheduled_sync.py`)
   - Every 10 minutes (configurable)
   - Processes all configured projects
   - Reads actual dates from Jira custom fields and stores in PostgreSQL

2. **During Webhook Updates** (`SyncJiraIssueUseCase`)
   - Real-time updates when issues change
   - Reads latest actual date values from Jira

**No calculation is performed during sync** - values are read directly from Jira where the listener has already set them.

## Docker Service

The `jira-sync-service` container automatically handles syncing with actual dates:

```yaml
jira-sync-service:
  image: jira_telegram_bot:v3
  command: python3 scripts/run_scheduled_sync.py
  environment:
    - SYNC_INTERVAL_MINUTES=10
    - SYNC_PROJECT_KEYS=["PROJ1","MYPROJECT","PROJ4","PROJ5"]
```

## Verification

### Check Database
```sql
SELECT 
    key,
    status,
    created_at,
    actual_start_date,
    actual_end_date,
    resolved_at
FROM jira_tasks_enhanced
WHERE project = 'MYPROJECT'
    AND actual_start_date IS NOT NULL
ORDER BY key
LIMIT 10;
```

### Check Jira Custom Fields
In Jira, verify that the custom fields are populated:
1. Open any issue
2. Check for "Actual Start Date" (customfield_10700)
3. Check for "Actual End Date" (customfield_10701)

## Error Handling

### Common Issues

1. **Missing Changelog/Worklog Data**
   - The script skips issues with no calculable dates
   - Logged as "skipped" in statistics

2. **Jira API Failures**
   - Individual issue failures are logged
   - Script continues processing remaining issues
   - Check logs for specific error messages

3. **Permission Issues**
   - Ensure Jira user has edit permission on issues
   - Custom fields must be editable by the integration user

## Monitoring

Check logs for sync operations:
```bash
# View sync service logs
docker logs -f jira_sync_service

# View backfill logs
tail -f logs.log | grep -i "actual"
```

## Future Enhancements

1. **Performance Optimization**
   - Batch update Jira fields to reduce API calls
   - Cache changelog/worklog data during sync

2. **Additional Calculations**
   - Lead time (actual_start to actual_end)
   - Cycle time (in_progress to done)
   - Compare actual vs planned dates

3. **Reporting**
   - Dashboard showing actual vs estimated dates
   - Velocity metrics based on actual completion dates
   - Bottleneck analysis using actual dates

## Testing

Run the backfill on a single test project first:

```python
# Modify scripts/backfill_actual_dates.py
project_keys = ["PROJ1"]  # Test project only
```

Then verify results before running on all projects.

## Rollback

If needed, rollback the migration:

```python
from jira_telegram_bot.adapters.repositories.postgres.database.migration_runner import MigrationRunner
from jira_telegram_bot.adapters.repositories.postgres.database.migrations.migration_010_add_actual_dates import Migration010AddActualDates

# Run rollback
runner = MigrationRunner(engine)
migration = Migration010AddActualDates()
runner.rollback_migration(migration)
```

## Questions or Issues?

Check the logs for detailed information:
- Application logs: `logs.log`
- Docker logs: `docker logs jira_sync_service`
- PostgreSQL logs: Check your PostgreSQL server logs
