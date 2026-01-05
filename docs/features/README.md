# Feature Documentation

Feature-specific documentation organized by functionality.

## Available Features

### 🔄 [Sync](sync/)
Jira project synchronization to PostgreSQL database.

- [Multi-Project Sync Guide](sync/multi-project-sync-guide.md)
- [Scripts Guide](sync/scripts-guide.md)

**Key Scripts:**
- `scripts/sync/sync_all_projects_last_month.py`
- `scripts/sync/sync_projects_date_range.py`
- `scripts/sync/run_scheduled_sync.py`

---

### 📊 [Team Evaluation](team_evaluation/)
Team performance metrics and evaluation tracking.

- [Team Evaluation Setup](team_evaluation/TEAM_EVALUATION_SETUP.md)

**Key Scripts:**
- `scripts/team_evaluation/setup_team_evaluation.py`
- `scripts/team_evaluation/run_team_evaluation.py`

---

### 🎯 [SynthPM](synth_pm/)
Multi-project synchronization service for SynthPM boards.

- [Implementation Summary](synth_pm/SYNTH_PM_IMPLEMENTATION_SUMMARY.md)
- [Docker Service Setup](synth_pm/SYNTH_PM_DOCKER_SERVICE.md)
- [Test Status](synth_pm/SYNTH_PM_TEST_STATUS.md)

**Key Scripts:**
- `scripts/notifications/run_synth_pm_service.py`
- `scripts/notifications/run_synth_pm.py`

---

### 📈 [Reports](reports/)
Automated report generation and scheduling.

**Key Scripts:**
- `scripts/reports/run_scheduled_reports.py`
- `scripts/reports/generate_reports_once.py`

---

### 🔔 [Notifications](notifications/)
Deadline notifications and alert services.

**Key Scripts:**
- `scripts/notifications/run_deadline_notifier.py`

---

## Documentation Organization

```
docs/
├── features/
│   ├── sync/                  - Synchronization features
│   ├── team_evaluation/       - Team evaluation system
│   ├── synth_pm/             - SynthPM multi-project sync
│   ├── reports/              - Report generation
│   └── notifications/        - Notification services
├── fixes/                    - Bug fixes and patches
└── infrastructure/           - Infrastructure setup
```

## Related Documentation

- [Main README](../../README.md) - Project overview
- [Database Sync Guide](../database-sync-guide.md) - Database synchronization
- [Analytics README](../README_ANALYTICS.md) - Analytics setup
- [Docker Setup](../../docker/README.md) - Docker configuration

## Contributing

When adding new features, create documentation in the appropriate feature directory:

1. Create feature directory: `docs/features/your-feature/`
2. Add README.md with usage instructions
3. Update this index
4. Update scripts README if adding scripts
