# Daily Task Tracker - Quick Start Guide

## 🚀 Quick Start

### 1. Enable the Service

Add to your `.env` or environment:
```bash
DAILY_TASK_TRACKER_ENABLED=true
DAILY_TASK_TRACKER_CRON_SCHEDULE="0 9 * * *"  # 9 AM daily
DAILY_TASK_TRACKER_TIMEZONE="Asia/Tehran"
DAILY_TASK_TRACKER_EXCLUDE_WEEKENDS=true
```

### 2. Start Docker Service

```bash
docker-compose up -d daily-task-tracker
```

### 3. Test Run

```bash
# Run once without waiting for schedule
docker-compose exec daily-task-tracker python3 scripts/run_daily_task_tracker.py --once
```

## 📱 User Experience

### Morning Notification (9 AM)

Users receive messages in Persian:

```
سلام! 👋
زمان بررسی روزانه تسک‌های شماست.
لطفاً به سوالات زیر پاسخ دهید:

───────────────────────────

📋 تسک: PCT-123
📝 عنوان: Implement login feature
📊 وضعیت: To Do
📅 اسپرینت: Sprint 10

چرا این تسک را شروع نکرده‌اید؟

[منتظر تایید] [مشکل فنی]
[اولویت دیگر] [نیازمندی ناقص]
[وابستگی آماده نیست] [سایر]
[درخواست زیرتسک] [رد کردن]
```

## 🔍 What Gets Checked

### Tasks That Trigger Notifications:

| Condition | Question | Action |
|-----------|----------|--------|
| **Target start passed** + Not started | Why haven't you started? | Record delay reason |
| **In Progress** | How many hours today? | Record time spent |
| **Done/Review** + No worklog | How many hours total? | Add worklog to Jira |
| **Moved Review→Backlog** by QA/Reporter | Notification only | Alert assignee |

## 🎛️ Configuration Options

### Cron Schedule Examples

```bash
# Daily at 9 AM
DAILY_TASK_TRACKER_CRON_SCHEDULE="0 9 * * *"

# Twice daily (9 AM and 2 PM)
DAILY_TASK_TRACKER_CRON_SCHEDULE="0 9,14 * * *"

# Monday to Friday at 9 AM
DAILY_TASK_TRACKER_CRON_SCHEDULE="0 9 * * 1-5"

# Every 2 hours during work hours (9 AM - 5 PM)
DAILY_TASK_TRACKER_CRON_SCHEDULE="0 9-17/2 * * *"
```

## 📊 Persian Button Options

### Delay Reasons
- منتظر تایید → Waiting for approval
- مشکل فنی → Technical blocker
- اولویت دیگر → Other priorities
- نیازمندی ناقص → Missing requirements
- وابستگی آماده نیست → Dependency not ready
- سایر → Other (custom text input)

### Hours
- ۱ ساعت → 1 hour
- ۲ ساعت → 2 hours
- ۳ ساعت → 3 hours
- ۴ ساعت → 4 hours
- ۶ ساعت → 6 hours
- ۸ ساعت → 8 hours
- سایر → Custom (numeric input)

## 🗂️ Data Storage

### Progress Reports Location
```
data/storage/daily_task_tracking.jsonl
```

### View Recent Reports
```bash
tail -20 data/storage/daily_task_tracking.jsonl | jq
```

## 🔧 Troubleshooting

### Check if Service is Running
```bash
docker-compose ps daily-task-tracker
```

### View Live Logs
```bash
docker-compose logs -f daily-task-tracker
```

### Test Without Docker
```bash
python scripts/run_daily_task_tracker.py --once
```

### Common Issues

| Problem | Solution |
|---------|----------|
| No messages sent | Check users have `telegram_user_chat_id` in user_config.json |
| Worklog not added | Verify Jira credentials and permissions |
| PO not notified | Check `po_username` in projects_info.json |
| Service not running | Check `DAILY_TASK_TRACKER_ENABLED=true` |

## 📝 User Setup Requirements

### In `user_config.json`:
```json
{
  "telegram_username": {
    "jira_username": "john.doe",
    "telegram_user_chat_id": 123456789,
    "telegram_username": "johndoe"
  }
}
```

### In `projects_info.json`:
```json
{
  "PROJECT_KEY": {
    "po_username": "jane.doe"
  }
}
```

## 🎯 Key Features

✅ **Fully Persian Interface** - All questions and buttons in Farsi  
✅ **Smart Task Detection** - Only shows tasks needing attention  
✅ **Worklog Automation** - Auto-logs to Jira  
✅ **Status Regression Alerts** - Notifies on Review→Backlog  
✅ **PO Integration** - Request subtasks directly  
✅ **Clean Architecture** - Fully testable and maintainable  
✅ **APScheduler** - No while loops, proper scheduling  

## 🔗 Related Services

- **Deadline Notifier**: Alerts on approaching deadlines
- **Synth PM**: Google Sheets sync
- **Daily Report**: Voice-to-text daily standups

## 📚 Full Documentation

See [README.md](./README.md) for complete architecture and details.
