"""
DEPRECATED: This file has been refactored according to Clean Architecture principles.

The functionality has been moved to:
- Entities: jira_telegram_bot/entities/jira_report.py
- Use Cases: jira_telegram_bot/use_cases/generate_jira_report_use_case.py
- Use Cases: jira_telegram_bot/use_cases/scheduled_report_use_case.py
- Services: jira_telegram_bot/adapters/services/jira_data_service.py
- Repositories: jira_telegram_bot/adapters/repositories/jira_report_repository.py
- Scheduler: jira_telegram_bot/frameworks/scheduler/ap_scheduler_service.py

For immediate report generation, use:
    python scripts/generate_reports_once.py

For scheduled report generation, use:
    python scripts/run_scheduled_reports.py

This file should not be used directly anymore.
"""
