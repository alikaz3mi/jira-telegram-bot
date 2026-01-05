# Scripts Directory

This directory contains utility scripts for managing the Jira Telegram Bot.

## Project Synchronization Scripts

### Quick Start

```bash
# 1. Check current sync status
make sync-check

# 2. Sync all projects from last month
make sync-last-month

# 3. Sync with custom options
make sync-custom ARGS='--days 7'
```

### Available Sync Scripts

#### `check_sync_status.py`
Display configured projects and their database sync status.

```bash
python scripts/check_sync_status.py
# OR
make sync-check
```

**Output:**
- List of configured projects
- Issues count per project in database
- Last sync times
- Recommendations for missing projects

#### `sync_all_projects_last_month.py`
Simple one-command sync for all projects from the last 30 days.

```bash
python scripts/sync_all_projects_last_month.py
# OR
make sync-last-month
```

**Features:**
- Syncs all configured projects automatically
- Fetches issues updated in last 30 days
- Prevents duplicates automatically
- Detailed logging per project

#### `sync_projects_date_range.py`
Flexible sync with command-line options.

```bash
# Sync last 7 days
python scripts/sync_projects_date_range.py --days 7
make sync-custom ARGS='--days 7'

# Sync from specific date
python scripts/sync_projects_date_range.py --since 2025-12-01
make sync-custom ARGS='--since 2025-12-01'

# Sync specific projects
python scripts/sync_projects_date_range.py --projects PROJ1 PROJ2 --days 14
make sync-custom ARGS='--projects PROJ1 PROJ2 --days 14'

# Full sync (all issues)
python scripts/sync_projects_date_range.py --full-sync
make sync-custom ARGS='--full-sync'
```

**Options:**
- `--projects`: Specific project keys (space-separated)
- `--days`: Number of days to look back (default: 30)
- `--since`: Start date in YYYY-MM-DD format
- `--full-sync`: Sync all issues regardless of date

## Configuration

Configure projects in `.env` file:

```env
# Comma-separated list of project keys
SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3,FOLLOWUP,PARSCHAT

# Sync interval for scheduled sync (minutes)
SYNC_INTERVAL_MINUTES=10

# Full or incremental sync
SYNC_FULL_SYNC=true
```

See `config/jira_sync.env.example` for detailed configuration.

## Duplicate Prevention

All sync scripts use PostgreSQL **upsert** to prevent duplicates:

- ✅ Safe to run multiple times
- ✅ Updates existing issues automatically
- ✅ Inserts new issues only
- ✅ Primary key: Jira issue key

No duplicate rows will be created when re-syncing the same data!

## Typical Workflows

### Initial Setup
```bash
# 1. Configure projects in .env
echo "SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3" >> .env

# 2. Full sync for first time
python scripts/sync_projects_date_range.py --full-sync

# 3. Verify
make sync-check
```

### Regular Updates
```bash
# Daily/weekly sync
make sync-last-month

# Or specific range
make sync-custom ARGS='--days 7'
```

### Adding New Projects
```bash
# 1. Add to .env
echo "SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3,NEWPROJ" >> .env

# 2. Sync new project
make sync-custom ARGS='--projects NEWPROJ --full-sync'

# 3. Verify
make sync-check
```

## Other Scripts

### `sync_projects.py`
Legacy sync script (full sync only).

```bash
python scripts/sync_projects.py
```

### `run_scheduled_sync.py`
Long-running service for automated sync.

```bash
python scripts/run_scheduled_sync.py
```

### Team Evaluation
- `setup_team_evaluation.py` - Initial setup
- `run_team_evaluation.py` - Run evaluation
- `backfill_team_evaluations.py` - Historical data

### Migration Scripts
- `run_migrations.py` - Database migrations
- `run_migration_008.py` - Specific migration
- `run_migration_011.py` - Specific migration

### Backfill Scripts
- `backfill_actual_dates.py` - Fill missing dates
- `backfill_calculation_logs.py` - Fill calculation logs
- `backfill_reviewed_at.py` - Fill review timestamps
- `backfill_task_tracking_fields.py` - Fill tracking fields

## Documentation

For detailed information:
- [Multi-Project Sync Guide](../docs/multi-project-sync-guide.md)
- [Database Sync Guide](../docs/database-sync-guide.md)

## Logging

All scripts log to:
- **Console**: Real-time output
- **Log files**: `logs.log.*` in project root

Example log output:
```
2026-01-05 10:30:00 - INFO - Starting multi-project synchronization
2026-01-05 10:30:05 - INFO - ✓ Successfully synced 45 issue(s) for PROJECT1
2026-01-05 10:35:00 - INFO - Total issues synced: 132
```

## Troubleshooting

### No projects found
```bash
# Check .env configuration
grep SYNC_PROJECT_KEYS .env

# Should output something like:
# SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3
```

### Sync fails
```bash
# Check status first
make sync-check

# Try syncing one project
make sync-custom ARGS='--projects PROJ1 --days 1'

# Check logs
tail -f logs.log.1
```

### Database connection errors
```bash
# Verify database is running
docker compose ps

# Check database settings in .env
grep DATABASE_URL .env
```
