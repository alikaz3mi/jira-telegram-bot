# Sync Scripts

Scripts for synchronizing Jira projects to PostgreSQL database.

## Scripts

### `check_sync_status.py`
Display configured projects and their database sync status.

```bash
python scripts/sync/check_sync_status.py
```

### `sync_all_projects_last_month.py`
Sync all configured projects for the last 30 days.

```bash
python scripts/sync/sync_all_projects_last_month.py
```

### `sync_projects_date_range.py`
Flexible sync with custom date ranges.

```bash
python scripts/sync/sync_projects_date_range.py --days 7
python scripts/sync/sync_projects_date_range.py --since 2025-12-01
python scripts/sync/sync_projects_date_range.py --projects PROJ1 PROJ2 --full-sync
```

### `run_scheduled_sync.py`
Long-running service for automated synchronization.

```bash
python scripts/sync/run_scheduled_sync.py
```

### `sync_projects.py`
Legacy full sync script.

```bash
python scripts/sync/sync_projects.py
```

### `sync_stories.py` / `sync_bugs_improvements.py`
Sync specific issue types to Google Sheets.

```bash
python scripts/sync/sync_stories.py
python scripts/sync/sync_bugs_improvements.py
```

### `sync_delay_reason.py`
Sync delay reasons for issues.

```bash
python scripts/sync/sync_delay_reason.py
```

## Configuration

Configure in `.env`:

```env
SYNC_PROJECT_KEYS=PROJ1,PROJ2,PROJ3
SYNC_INTERVAL_MINUTES=10
SYNC_FULL_SYNC=true
```

## Documentation

See [docs/features/sync/](../../docs/features/sync/) for detailed documentation.
