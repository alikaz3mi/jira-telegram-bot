# Scripts Directory

Organized utility scripts for the Jira Telegram Bot project.

## Directory Structure

```
scripts/
├── sync/              - Jira project synchronization scripts
├── notifications/     - Notification services (deadline notifier, SynthPM)
├── reports/           - Report generation scripts
├── team_evaluation/   - Team evaluation and metrics
├── backfill/          - Data backfill utilities
├── migration/         - Database migration runners
├── debug_tools/       - Debug and inspection utilities
├── testing/           - Test scripts
└── helpers/           - Shared helper modules
```

## Quick Reference

### Sync Operations
```bash
# Check sync status
python scripts/sync/check_sync_status.py

# Sync all projects (last month)
python scripts/sync/sync_all_projects_last_month.py

# Custom sync
python scripts/sync/sync_projects_date_range.py --days 7

# Scheduled sync service
python scripts/sync/run_scheduled_sync.py
```

### Services
```bash
# Deadline notifier
python scripts/notifications/run_deadline_notifier.py

# SynthPM service
python scripts/notifications/run_synth_pm_service.py

# Reports
python scripts/reports/run_scheduled_reports.py
```

### Team Evaluation
```bash
# Setup
python scripts/team_evaluation/setup_team_evaluation.py

# Run evaluation
python scripts/team_evaluation/run_team_evaluation.py
```

## Documentation

Detailed feature documentation is located in `docs/features/`:

- **Sync**: [docs/features/sync/](../docs/features/sync/)
- **Team Evaluation**: [docs/features/team_evaluation/](../docs/features/team_evaluation/)
- **SynthPM**: [docs/features/synth_pm/](../docs/features/synth_pm/)
- **Reports**: [docs/features/reports/](../docs/features/reports/)

## Running from Docker

Most scripts are designed to run in Docker containers. See `docker-compose.yml` for service definitions.

## Environment Variables

Scripts read configuration from `.env` file. See `config/*.env.example` for examples.
