# Deadline Notifier Configuration

The deadline notifier can be configured using environment variables or settings classes. All configuration follows the Clean Architecture principles with proper dependency injection.

## Environment Variables

### Basic Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEADLINE_NOTIFIER_LOOKAHEAD_DAYS` | `7` | Number of days to look ahead for deadlines |
| `DEADLINE_NOTIFIER_ADDITIONAL_JQL` | `""` | Additional JQL filter to apply to deadline queries |
| `DEADLINE_NOTIFIER_CRON_SCHEDULE` | `"0 9 * * *"` | Cron schedule for deadline notifications (default: 9 AM daily) |
| `DEADLINE_NOTIFIER_GROUP_NOTIFICATION_USERNAMES` | `["ali_kazemi", "a_heravi"]` | JSON array of Jira usernames who receive filtered group notifications |

### Group Chat Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_GROUP_CHAT_IDS` | `""` | Comma-separated list of Telegram group chat IDs for notifications |

## Example Configuration

### Environment Variables (.env file)
```env
# Deadline Notifier Settings
DEADLINE_NOTIFIER_LOOKAHEAD_DAYS=7
DEADLINE_NOTIFIER_ADDITIONAL_JQL="project = PARSCHAT AND Sprint in openSprints() and assignee is not EMPTY"
DEADLINE_NOTIFIER_CRON_SCHEDULE="0 9 * * *"
DEADLINE_NOTIFIER_GROUP_NOTIFICATION_USERNAMES=["ali_kazemi", "a_heravi"]

# Group Chat Configuration
TELEGRAM_GROUP_CHAT_IDS="-1001234567890,-1009876543210"
```

### Shell Export
```bash
export DEADLINE_NOTIFIER_LOOKAHEAD_DAYS=7
export DEADLINE_NOTIFIER_GROUP_NOTIFICATION_USERNAMES='["ali_kazemi", "a_heravi"]'
export TELEGRAM_GROUP_CHAT_IDS="-1001234567890,-1009876543210"
```

## Notification Behavior

### Personal Notifications
- Sent to all issue assignees for their personal assigned issues
- Includes all issue types (stories, tasks, subtasks)
- Sent to individual Telegram chat IDs

### Group Notifications
- Sent to configured group chat IDs via `TELEGRAM_GROUP_CHAT_IDS`
- Also sent to personal chat IDs of users listed in `GROUP_NOTIFICATION_USERNAMES`
- **Filtered content**: For users in `GROUP_NOTIFICATION_USERNAMES`, only stories and tasks are included (subtasks are excluded)
- Only urgent issues are included (overdue, today, urgent priority)

## Usage Examples

### Adding a New User to Filtered Notifications
```bash
export DEADLINE_NOTIFIER_GROUP_NOTIFICATION_USERNAMES='["ali_kazemi", "a_heravi", "new_user"]'
```

### Setting Custom Lookahead Period
```bash
export DEADLINE_NOTIFIER_LOOKAHEAD_DAYS=14
```

### Custom JQL Filter
```bash
export DEADLINE_NOTIFIER_ADDITIONAL_JQL="project in (PARSCHAT, VANGUARD) AND Sprint in openSprints()"
```

### Multiple Group Chats
```bash
export TELEGRAM_GROUP_CHAT_IDS="-1001234567890,-1009876543210,-1001111111111"
```

## Testing Configuration

Run the configuration test script to verify your settings:
```bash
python scripts/tests/test_deadline_notifier_configuration.py
```

## Architecture

The deadline notifier follows Clean Architecture principles:

- **Settings**: `DeadlineNotifierSettings` class handles environment variable parsing
- **Use Case**: `SendDeadlineAlertsUseCase` contains the business logic
- **Dependency Injection**: All dependencies are properly injected via the Lagom container
- **User Configuration**: Group chat IDs and user mappings are managed through the `UserConfigInterface`

## Migration from Hardcoded Values

If you previously had hardcoded usernames in the code, you can now configure them via environment variables. The system will automatically:

1. Read group chat IDs from `TELEGRAM_GROUP_CHAT_IDS`
2. Apply filtered notifications (excluding subtasks) to users in `GROUP_NOTIFICATION_USERNAMES`
3. Send notifications to both actual group chats and personal chats of configured users
