# Jira Report System

This document describes the comprehensive Jira reporting system that has been refactored according to Clean Architecture principles.

## Architecture Overview

The system follows Clean Architecture with clear separation of concerns:

### Entities (`jira_telegram_bot/entities/`)
- `jira_report.py`: Core business entities including `JiraIssueDetail`, `WorklogEntry`, `LinkedIssue`, and `ProjectReport`

### Use Cases (`jira_telegram_bot/use_cases/`)
- `generate_jira_report_use_case.py`: Core business logic for report generation
- `scheduled_report_use_case.py`: Orchestrates scheduled report generation
- `interfaces/`: Interface definitions for dependency injection

### Adapters (`jira_telegram_bot/adapters/`)
- `services/jira_data_service.py`: Service for fetching comprehensive Jira data
- `repositories/jira_report_repository.py`: PostgreSQL persistence layer

### Frameworks (`jira_telegram_bot/frameworks/`)
- `scheduler/ap_scheduler_service.py`: APScheduler implementation for job scheduling

## Features

### Enhanced Data Collection
The new system collects comprehensive issue information including:
- **Worklog entries**: Time tracking with author, duration, and comments
- **Linked issues**: Issue relationships and dependencies
- **Release information**: Fix versions and release planning data
- **Time estimates**: Original and remaining time estimates
- **All existing fields**: Epic links, sprints, components, labels, etc.

### Scheduled Execution
- Runs every 30 minutes automatically
- Configurable intervals
- Graceful shutdown handling
- Error resilience

### Database Storage
- PostgreSQL backend with enhanced schema
- JSON columns for complex data (worklogs, linked issues)
- Automatic schema migrations
- Upsert operations for data freshness

## Usage

### One-time Report Generation
```bash
python scripts/generate_reports_once.py
```

### Scheduled Report Service
```bash
python scripts/run_scheduled_reports.py
```

### Docker Deployment
```bash
docker-compose up jira-report-scheduler
```

## Configuration

### Project Keys
Configure which projects to monitor in `config_dependency_injection.py`:
```python
container[ScheduledReportUseCase] = Singleton(
    lambda c: ScheduledReportUseCase(
        report_use_case=c[GenerateJiraReportUseCase],
        scheduler_service=c[SchedulerServiceInterface],
        project_keys=["PARSCHAT", "PCT", "YOUR_PROJECT"],  # Add your projects here
    )
)
```

### Database Configuration
Set environment variables or update `settings/postgre_db_settings.py`:
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

### Schedule Interval
Modify the interval in `scripts/run_scheduled_reports.py`:
```python
await self._scheduled_report_use_case.setup_scheduled_reports(
    interval_minutes=30  # Change this value
)
```

## Database Schema

The system creates a `jira_tasks_enhanced` table with the following fields:

### Basic Fields
- `key` (Primary Key)
- `summary`, `description`, `epic_name`
- `task_type`, `assignee`, `reporter`, `priority`, `status`
- `created_at`, `updated_at`, `resolved_at`
- `target_start`, `target_end`

### Enhanced Fields
- `story_points`
- `components` (Array)
- `labels` (Array)
- `release` (Array of fix versions)
- `last_sprint`, `sprint_repeats`
- `original_estimate`, `remaining_estimate`
- `worklog_entries` (JSON)
- `linked_issues` (JSON)
- `last_synced`

## Dependency Injection

The system uses Lagom for dependency injection with the following bindings:

```python
container[JiraDataServiceInterface] = JiraDataService
container[JiraReportRepositoryInterface] = JiraReportRepository
container[SchedulerServiceInterface] = APSchedulerService
container[GenerateJiraReportUseCase] = ...
container[ScheduledReportUseCase] = ...
```

## Testing

Run the unit tests:
```bash
python -m pytest tests/use_cases/test_generate_jira_report_use_case.py -v
```

## Migration from Legacy System

The old `report.py` file has been deprecated. The new system provides:
- Better error handling and logging
- Proper dependency injection
- Comprehensive test coverage
- Scheduled execution
- Enhanced data collection
- Clean Architecture compliance

## Troubleshooting

### Common Issues

1. **Database Connection**: Ensure PostgreSQL is running and credentials are correct
2. **Jira Authentication**: Verify Jira credentials in settings
3. **Missing Dependencies**: Run `pip install -r requirements.txt`
4. **Schedule Not Running**: Check logs for scheduler service errors

### Logs
All operations are logged using the configured logger. Check logs for:
- Report generation progress
- Database operations
- Scheduler status
- Error details

## Development

### Adding New Fields
1. Update the `JiraIssueDetail` entity
2. Modify the `JiraDataService` to extract the field
3. Update the database model in `JiraReportRepository`
4. Add migration logic if needed

### Custom Schedulers
Implement the `SchedulerServiceInterface` to use different scheduling backends:
```python
class CustomSchedulerService(SchedulerServiceInterface):
    async def schedule_recurring_job(self, job_func, interval_minutes, job_name):
        # Your implementation
        pass
```
