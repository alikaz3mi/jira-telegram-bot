# Deadline Notifier Architecture

## Overview

The Deadline Notifier is an automated system that monitors Jira issues with approaching deadlines and sends notifications to assignees via Telegram. It follows Clean Architecture principles and runs as a scheduled cron job.

## Architecture Components

### Domain Layer (Entities)

#### `DeadlineAlert` 
- Core entity representing a deadline alert
- Contains issue metadata, deadline information, and urgency calculations
- Provides computed properties for urgency level and deadline status

### Use Cases Layer

#### `SendDeadlineAlertsUseCase`
- Main orchestrator for the deadline notification process
- Coordinates between Jira data retrieval, user configuration, and notification sending
- Ensures idempotency by tracking sent notifications

### Interface Layer

#### `TaskManagerRepositoryInterface`
- Extended with `get_issues_with_approaching_deadlines()` method
- Handles JQL queries for deadline-based issue retrieval

#### `UserConfigInterface` 
- Extended with `get_all_user_configs()` and `get_group_chat_ids()` methods
- Manages mapping between Jira users and Telegram chat IDs

#### `TelegramNotifierInterface`
- Handles formatting and sending of Telegram notifications
- Supports both personal and group notifications

#### `NotificationLogRepositoryInterface`
- Manages notification history to prevent duplicate alerts
- Provides cleanup functionality for log maintenance

### Adapter Layer

#### `TelegramNotifier`
- Implements Telegram API communication
- Formats messages with appropriate urgency indicators and user mentions
- Handles both personal and group notification scenarios

#### `FileNotificationLogRepository`
- File-based storage for notification logs using JSON Lines format
- Provides efficient lookups and cleanup capabilities

#### Jira Repository Extensions
- Both `JiraServerRepository` and `JiraCloudRepository` extended
- Implements deadline-based JQL queries using `duedate` and `customfield_10110` (Target End)

### Framework Layer

#### `CronJob`
- Scheduler implementation using croniter library
- Supports graceful shutdown and error handling
- Configurable via cron expressions

## Data Flow

1. **Cron Job Trigger**: Scheduler triggers based on configured cron expression
2. **Issue Retrieval**: Query Jira for issues with approaching deadlines
3. **Alert Creation**: Convert Jira issues to `DeadlineAlert` entities
4. **User Mapping**: Map Jira assignees to Telegram users/groups
5. **Idempotency Check**: Verify if notifications already sent today
6. **Notification Sending**: Send formatted messages to Telegram
7. **Logging**: Record sent notifications for future idempotency checks

## Configuration

### Environment Variables

- `DEADLINE_NOTIFIER_CRON`: Cron schedule (default: "0 9 * * *")
- `DEADLINE_NOTIFIER_LOOKAHEAD_DAYS`: Days ahead to check (default: 7)
- `DEADLINE_NOTIFIER_ADDITIONAL_JQL`: Additional JQL filter
- `TELEGRAM_GROUP_CHAT_IDS`: Comma-separated group chat IDs

### Urgency Levels

- **Overdue**: Past due date
- **Today**: Due today
- **Urgent**: Due within 1 day
- **High**: Due within 3 days
- **Medium**: Due within 7 days
- **Low**: Due beyond 7 days

## Message Formatting

### Personal Notifications
- Individual messages sent to assignee's personal chat
- Includes full issue details with direct links
- Urgency-based emoji indicators

### Group Notifications
- Summary messages for urgent issues only (overdue, today, urgent)
- User mentions when possible
- Grouped by urgency level

## Idempotency

The system prevents duplicate notifications by:
- Logging each sent notification with issue key, chat ID, and date
- Checking log before sending new notifications
- Using date-based deduplication (one notification per issue per day)

## Deployment Options

### Standalone Script
```bash
python scripts/run_deadline_notifier.py --once
python scripts/run_deadline_notifier.py --cron "*/30 * * * *"
```

### Docker Container
```dockerfile
FROM python:3.12-slim
# ... setup steps ...
CMD ["python", "scripts/run_deadline_notifier.py"]
```

### Kubernetes CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: deadline-notifier
spec:
  schedule: "0 9 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: notifier
            image: jira-telegram-bot:latest
            command: ["python", "scripts/run_deadline_notifier.py", "--once"]
```

## Error Handling

- Graceful handling of Jira API failures
- Telegram API retry logic
- Logging of all errors for debugging
- Continuation of processing despite individual failures

## Testing Strategy

- Unit tests for all use cases and adapters
- Mock implementations for external dependencies
- Integration tests with test Jira instances
- End-to-end tests with actual Telegram notifications

## Monitoring

- Comprehensive logging at all levels
- Statistics tracking for sent notifications
- Health checks for cron job status
- Error rate monitoring

## Future Enhancements

1. **Escalation Rules**: Send notifications to managers for overdue items
2. **Customizable Templates**: User-specific message formatting
3. **Slack Integration**: Support for Slack notifications
4. **Dashboard**: Web interface for monitoring and configuration
5. **Smart Scheduling**: AI-based optimal notification timing
