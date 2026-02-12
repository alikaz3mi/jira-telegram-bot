# Scripts Organization Summary

The scripts directory has been reorganized for better maintainability.

## New Structure

```
scripts/
├── README.md                     # Main scripts overview
├── sync/                         # ✅ Jira synchronization
│   ├── README.md
│   ├── check_sync_status.py
│   ├── run_scheduled_sync.py
│   ├── sync_all_projects_last_month.py ⭐ NEW
│   ├── sync_projects_date_range.py     ⭐ NEW
│   ├── sync_projects.py
│   ├── sync_stories.py
│   ├── sync_bugs_improvements.py
│   └── sync_delay_reason.py
│
├── notifications/                # ✅ Service daemons
│   ├── README.md
│   ├── run_deadline_notifier.py
│   ├── run_synth_pm_service.py
│   └── run_synth_pm.py
│
├── reports/                      # ✅ Report generation
│   ├── README.md
│   ├── run_scheduled_reports.py
│   ├── generate_reports_once.py
│   └── generate_random_tasks.py
│
├── team_evaluation/              # ✅ Team metrics
│   ├── README.md
│   ├── setup_team_evaluation.py
│   ├── run_team_evaluation.py
│   ├── run_team_evaluation.sh
│   └── manual_team_evaluation.py
│
├── backfill/                     # ✅ Data backfill
│   ├── README.md
│   ├── backfill_actual_dates.py
│   ├── backfill_calculation_logs.py
│   ├── backfill_reviewed_at.py
│   ├── backfill_task_tracking_fields.py
│   ├── backfill_team_evaluations.py
│   └── populate_delay_reasons.py
│
├── migration/                    # ✅ Database migrations
│   ├── README.md
│   ├── run_migration_008.py
│   └── run_migration_011.py
│
├── debug_tools/                  # ✅ Debug utilities
│   ├── README.md
│   ├── check_boards.py
│   ├── check_calculation_logs.py
│   ├── check_task_tracking_progress.py
│   ├── debug_epic_fields.py
│   ├── demo_synth_pm_filtering.py
│   ├── view_jira_tasks_delay_reasons.py
│   └── find_recent_sprints.py
│
├── testing/                      # ✅ Test scripts
│   ├── README.md
│   ├── test_delay_reason_extraction.py
│   ├── test_delay_reason_simple.py
│   ├── test_department_dependencies.py
│   ├── test_epic_sync.py
│   ├── test_sprint_closed_webhook.py
│   ├── test_sprint_closed_webhook.sh
│   └── test_synth_pm_filtering.py
│
├── helpers/                      # Shared utilities
└── run_jobs.sh                   # Legacy job runner
```

## Documentation Structure

```
docs/
├── features/                     # ✅ Feature-specific docs
│   ├── README.md                 # Feature index ⭐ NEW
│   ├── sync/                     # Sync documentation
│   │   ├── multi-project-sync-guide.md
│   │   └── scripts-guide.md
│   ├── team_evaluation/          # Team eval docs
│   │   └── TEAM_EVALUATION_SETUP.md
│   ├── synth_pm/                 # SynthPM docs
│   │   ├── SYNTH_PM_IMPLEMENTATION_SUMMARY.md
│   │   ├── SYNTH_PM_DOCKER_SERVICE.md
│   │   └── SYNTH_PM_TEST_STATUS.md
│   ├── reports/                  # Reports docs
│   └── notifications/            # Notifications docs
├── fixes/                        # Bug fix documentation
└── infrastructure/               # Infrastructure docs
```

## Updated Files

### Docker Compose
✅ Updated paths in `docker-compose.yml`:
- `jira-sync-service`: `scripts/sync/run_scheduled_sync.py`
- `synth-pm-multi-project-service`: `scripts/notifications/run_synth_pm_service.py`
- `deadline-notifier-service`: `scripts/notifications/run_deadline_notifier.py` (uncommented)
- `scheduled-reports-service`: `scripts/reports/run_scheduled_reports.py` (added)

### Makefile
✅ Updated paths:
- `sync-check`: `scripts/sync/check_sync_status.py`
- `sync-last-month`: `scripts/sync/sync_all_projects_last_month.py`
- `sync-custom`: `scripts/sync/sync_projects_date_range.py`

## Quick Reference

### Check Sync Status
```bash
make sync-check
# OR
python scripts/sync/check_sync_status.py
```

### Sync Projects
```bash
make sync-last-month
# OR
python scripts/sync/sync_all_projects_last_month.py
```

### Custom Sync
```bash
make sync-custom ARGS='--days 7'
# OR
python scripts/sync/sync_projects_date_range.py --days 7
```

### Run Services
```bash
# Start all services
docker compose up -d

# View specific service
docker compose logs -f jira-sync-service
docker compose logs -f synth-pm-multi-project-service
```

## Benefits

✅ **Organized** - Scripts grouped by feature/purpose  
✅ **Documented** - Each subdirectory has README  
✅ **Discoverable** - Easy to find related scripts  
✅ **Maintainable** - Clear separation of concerns  
✅ **Clean Architecture** - Follows project conventions  

## Migration Notes

All script paths have been updated in:
- ✅ docker-compose.yml
- ✅ Makefile
- ✅ Documentation links

No code changes required - only paths updated!
