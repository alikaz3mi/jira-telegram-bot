# Deadline Notifications Feature

The deadline notification system automatically alerts users and teams about approaching task deadlines via Telegram.

## 📄 Documentation Files

- **deadline-notifier-configuration.md** - Complete configuration guide including environment variables, user settings, and notification rules
- **deadline_notifier.md** - Technical architecture, implementation details, and system design

## 🔧 Key Features

- **Personal Notifications**: Direct alerts to task assignees
- **Group Notifications**: Team-wide deadline alerts
- **Smart Filtering**: Holiday/weekend awareness, active sprint filtering
- **Configurable Schedule**: Cron-based scheduling with customizable parameters
- **Duplicate Prevention**: Prevents notification spam with logging system

## ⚙️ Configuration

The deadline notifier uses environment variables for configuration:

- `DEADLINE_NOTIFIER_LOOKAHEAD_DAYS` - Days to look ahead for deadlines
- `DEADLINE_NOTIFIER_ADDITIONAL_JQL` - Additional JQL filters
- `DEADLINE_NOTIFIER_CRON_SCHEDULE` - Cron schedule for notifications
- `DEADLINE_NOTIFIER_GROUP_NOTIFICATION_USERNAMES` - Specific users for filtered group notifications

## 🚀 Getting Started

1. Read the configuration guide for setup instructions
2. Configure environment variables
3. Set up Telegram bot integration
4. Configure user mappings between Jira and Telegram
5. Test with sample notifications

For detailed setup instructions, see `deadline-notifier-configuration.md`.