# SynthPM Multi-Project Synchronization Service

This document describes the Docker-based multi-project synchronization service for SynthPM.

## Overview

The SynthPM Multi-Project Sync Service runs as a Docker container that automatically synchronizes features between Google Sheets and Jira for multiple projects. Each project can have its own:

- Sync interval (how often to sync)
- Developer board and optional PM board
- Status mappings
- Minimum status requirements for task creation
- Telegram notification settings

## Docker Service Configuration

### docker-compose.yml

```yaml
synth-pm-multi-project-service:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: synth_pm_multi_project
  image: jira_telegram_bot:v3
  volumes:
    - .:/app
  command: >
    python3 scripts/run_synth_pm_service.py
  restart: always
  environment:
    # Project keys to sync (comma-separated or JSON array)
    # Leave empty to sync all projects in config
    - SYNTH_PM_PROJECT_KEYS=
    # Or specify specific projects:
    # - SYNTH_PM_PROJECT_KEYS=MYPROJECT,PROJECT2
    # Or as JSON:
    # - SYNTH_PM_PROJECT_KEYS=["MYPROJECT","PROJECT2"]
  networks:
    - jira-bot-network
```

### Environment Variables

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `SYNTH_PM_PROJECT_KEYS` | Projects to sync | `MYPROJECT,PROJ2` or `["MYPROJECT"]` | All projects |
| `SYNTH_PM_TELEGRAM_BOT_TOKEN` | Telegram bot token (per project) | `123456:ABC...` | Required |
| `SYNTH_PM_TELEGRAM_CHANNEL_ID` | Telegram channel ID (per project) | `-100123456789` | Required |
| `SYNTH_PM_TELEGRAM_GROUP_ID` | Telegram group ID (per project) | `-100987654321` | Required |

## Project Configuration

### 1. Story Sync Config (`config/story_sync_config.json`)

```json
{
  "projects": [
    {
      "project_key": "MYPROJECT",
      "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
      "google_sheets_token_path": "pm-684f8662ca98.json",
      "boards": {
        "developer_board": {
          "jira_board_key": "MYPROJECT",
          "sheet_name": "MyProject Features",
          "data_range": "A2:AY",
          "enabled": true
        },
        "pm_board": {
          "jira_board_key": "PROJ2",
          "sheet_name": "Release Notes",
          "data_range": "A2:AO",
          "enabled": true
        }
      },
      "telegram": {
        "bot_token_env": "SYNTH_PM_TELEGRAM_BOT_TOKEN",
        "channel_id_env": "SYNTH_PM_TELEGRAM_CHANNEL_ID",
        "group_id_env": "SYNTH_PM_TELEGRAM_GROUP_ID"
      },
      "sync_settings": {
        "status_trigger_value": "۲",
        "sync_interval_minutes": 5,
        "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی"
      }
    }
  ]
}
```

### 2. Projects Info (`jira_telegram_bot/settings/projects_info.json`)

```json
{
  "MYPROJECT": {
    "project_info": { ... },
    "status_mapping": {
      "google_sheet_to_jira": {
        "۱. ثبت و اولویت بندی": "BACKLOG",
        "۵. آماده پیاده سازی فنی": "REOPENED",
        "۶. در حال پیاده سازی": "IN PROGRESS",
        ...
      },
      "jira_to_google_sheet": {
        "BACKLOG": "۱. ثبت و اولویت بندی",
        "IN PROGRESS": "۶. در حال پیاده سازی",
        ...
      }
    },
    "sprint_configuration": { ... },
    "departments": { ... },
    "components": [ ... ],
    "assignees": [ ... ]
  }
}
```

## Feature Validation

The service validates features before creating Jira tasks. A feature must meet ALL of these requirements:

✅ **Non-empty title** - Task title must be filled  
✅ **Status threshold** - Status must be at or above `minimum_status_for_task_creation`  
✅ **Assignees** - At least one person must be assigned  
✅ **Sprint** - Must have a sprint defined  
✅ **Departments** - At least one component/department must be selected (AI, Backend, Frontend, DevOps, UI/UX)  
✅ **Dates** - Must have at least one date (implementation start, target end, or due date)

### Validation Examples

**✅ Valid Feature:**
```
Status: ۶. در حال پیاده سازی
Assignees: John, Jane
Sprint: Sprint-5
Components: AI, Backend
Start Date: 2024-01-15
```

**❌ Invalid - Status Too Low:**
```
Status: ۲. تحلیل مسئله و RFP (Below "۵. آماده پیاده سازی فنی")
→ Skipped: Row 15 ('Feature X'): Status below minimum
```

**❌ Invalid - No Assignees:**
```
Assignees: (empty)
→ Skipped: Row 23: No assignees/involved people defined
```

**❌ Invalid - No Department:**
```
AI: ☐  Backend: ☐  Frontend: ☐  DevOps: ☐  UI/UX: ☐
→ Skipped: Row 45: No department/component defined
```

## Running the Service

### Start Service

```bash
# Start all services including synth-pm
docker-compose up -d synth-pm-multi-project-service

# View logs
docker-compose logs -f synth-pm-multi-project-service

# Check status
docker-compose ps synth-pm-multi-project-service
```

### Sync Specific Projects Only

Edit `docker-compose.yml` to specify projects:

```yaml
environment:
  - SYNTH_PM_PROJECT_KEYS=MYPROJECT,PROJECT2
```

Then restart:
```bash
docker-compose restart synth-pm-multi-project-service
```

### Manual Sync (Outside Docker)

```bash
# Sync all projects once
python scripts/run_synth_pm.py sync

# Sync specific project
python scripts/run_synth_pm.py sync --project MYPROJECT

# List available projects
python scripts/run_synth_pm.py list-projects

# Test connections
python scripts/run_synth_pm.py test --project MYPROJECT
```

## Service Behavior

### Multi-Project Independent Sync

Each project runs on its own schedule:
- **Project A**: Syncs every 5 minutes
- **Project B**: Syncs every 10 minutes  
- **Project C**: Syncs every 15 minutes

All projects run independently and concurrently.

### Sync Workflow

For each project, every sync cycle:

1. **Fetch features** from Google Sheets developer board
2. **Validate** each feature against requirements
3. **Create/Update** PM board tasks (if PM board enabled)
4. **Create/Update** Developer board tasks (if status allows)
5. **Sync release notes** (if PM board enabled)
6. **Post to Telegram** (for status changes)
7. **Log results** (created, updated, skipped, errors)

### Sync Results

Each sync reports:
```
[MYPROJECT] Sync completed - 
  Created: 3 PM, 5 dev | 
  Updated: 2 PM, 8 dev | 
  Skipped: 4 | 
  Errors: 0
```

Skipped features are logged with specific reasons:
```
Row 15 ('Feature X'): Status below minimum required status
Row 23 ('Feature Y'): No assignees/involved people defined
Row 45 ('Feature Z'): No department/component defined
```

## Monitoring & Debugging

### View Real-time Logs

```bash
# All projects
docker-compose logs -f synth-pm-multi-project-service

# Last 100 lines
docker-compose logs --tail=100 synth-pm-multi-project-service

# Since timestamp
docker-compose logs --since 2024-01-01T10:00:00 synth-pm-multi-project-service
```

### Check Service Health

```bash
# Is container running?
docker ps | grep synth_pm_multi_project

# Container stats
docker stats synth_pm_multi_project

# Restart if needed
docker-compose restart synth-pm-multi-project-service
```

### Common Issues

**Issue: Service exits immediately**
- Check logs: `docker-compose logs synth-pm-multi-project-service`
- Verify environment variables are set correctly
- Ensure Google Sheets credentials exist

**Issue: No projects syncing**
- Verify `story_sync_config.json` has projects defined
- Check `developer_board.enabled` is `true`
- Verify project keys in `SYNTH_PM_PROJECT_KEYS` match config

**Issue: High skip rate**
- Review validation requirements
- Check `minimum_status_for_task_creation` setting
- Ensure features have required fields filled

## Testing

### Run Unit Tests

```bash
# All validation tests
python -m pytest tests/unit_tests/adapters/test_synth_pm_validation.py -v

# Multi-project sync tests
python -m pytest tests/unit_tests/adapters/test_synth_pm_multi_project_sync.py -v

# Integration tests
python -m pytest tests/integration/test_synth_pm_feature_validation.py -v
```

### Run Specific Test

```bash
python -m pytest tests/unit_tests/adapters/test_synth_pm_validation.py::TestFeatureValidation::test_validate_status_below_minimum -v
```

## Adding a New Project

1. **Add to `story_sync_config.json`:**
```json
{
  "project_key": "NEWPROJECT",
  "spreadsheet_id": "...",
  "boards": { ... },
  "telegram": { ... },
  "sync_settings": {
    "sync_interval_minutes": 10,
    "minimum_status_for_task_creation": "۵. آماده پیاده سازی فنی"
  }
}
```

2. **Add to `projects_info.json`:**
```json
{
  "NEWPROJECT": {
    "project_info": { ... },
    "status_mapping": { ... },
    ...
  }
}
```

3. **Set environment variables** (if using dedicated Telegram bot):
```bash
SYNTH_PM_NEWPROJECT_TELEGRAM_BOT_TOKEN=...
SYNTH_PM_NEWPROJECT_TELEGRAM_CHANNEL_ID=...
SYNTH_PM_NEWPROJECT_TELEGRAM_GROUP_ID=...
```

4. **Restart service:**
```bash
docker-compose restart synth-pm-multi-project-service
```

## Performance Considerations

- **Concurrent Projects**: All projects sync independently, no blocking
- **Rate Limiting**: Google Sheets API has quotas; adjust sync intervals accordingly
- **Memory Usage**: ~50-100MB per project (varies with data size)
- **CPU Usage**: Minimal during idle, spikes during sync cycles

## Best Practices

1. **Sync Intervals**: Set based on team activity
   - Active development: 5-10 minutes
   - Maintenance mode: 30-60 minutes

2. **Validation**: Adjust `minimum_status_for_task_creation` per project needs

3. **Monitoring**: Review logs daily for patterns in skipped/errored features

4. **Testing**: Always test configuration changes with `test` command first

5. **Backups**: Keep backups of config files before changes
