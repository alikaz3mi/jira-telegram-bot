---
mode: agent
description: Add a cron-driven Jira-deadline notifier that posts to Telegram users & groups
tools: [terminalLastCommand, githubRepo]
---

# 🛠️ Goal
Implement an automated pipeline that **every N minutes** (configurable cron, containerised) does:

1. Pull all Jira issues whose *due date* (or *Target End*) is within a configurable horizon (default = 7 days) **via the already-existing `TaskManagerRepositoryInterface`** (located at `jira_telegram_bot/use_cases/interfaces/task_manager_repository_interface.py`).
2. Obtain mapping information (Telegram chat IDs for users / groups) from **`UserConfigInterface`** (`jira_telegram_bot/use_cases/interfaces/user_config_interface.py`).
3. For each issue, compute the “days left” value.
4. Post a formatted message to:
   * Each assignee’s personal Telegram chat.
   * Every Telegram group the bot is in, tagging assignees when possible.
5. Idempotent: never send duplicate notifications for the same issue/day — **persist a simple log in a local file** (e.g. `data/notifier_log.jsonl`) through `FileNotificationLogRepository`.

## 📝 Interactive variables
* `${input:cron_schedule:CRON expression (e.g. "*/30 * * * *")}`
* `${input:lookahead_days:Number of days ahead to consider (default 7)}`
* `${input:jira_filter_jql:Additional JQL filter (optional)}`

## 🔄 Workflow
1. **Domain Entity**
   * `DeadlineAlert` (`jira_telegram_bot/entities/deadline_alert.py`) – unchanged.
2. **Interfaces (reuse / add)**
   * **Reuse** `TaskManagerRepositoryInterface` for Jira access (implement `JiraTaskManagerRepository` adapter if one isn’t present).
   * **Reuse** `UserConfigInterface` to resolve user/group chat IDs.
   * **Add** `NotificationLogRepositoryInterface` (file-based implementation).
3. **Use Case**
   * `SendDeadlineAlertsUseCase` (async) depends on:
     * `TaskManagerRepositoryInterface`: jira_telegram_bot/use_cases/interfaces/task_manager_repository_interface.py. must be used and expanded if necessary
     * `UserConfigInterface: jira_telegram_bot/use_cases/interfaces/user_config_interface.py. must be used and expanded if necessary
     * `TelegramNotifierInterface: must be implementated
     * `NotificationLogRepositoryInterface`: must be implemented
4. **Adapters**
   * `TelegramNotifier` (python-telegram-bot 20.x wrapper)
   * `FileNotificationLogRepository` – append-only JSON Lines file. path: `jira_telegram_bot/adapters/repositories/file_storage/file_notification_log_repository.py
5. **Scheduler**
   * `frameworks/scheduler/cron_job.py` – unchanged
6. **Dependency Injection**
   * Bind existing Jira repository implementation to `TaskManagerRepositoryInterface`
   * Bind existing user-config adapter to `UserConfigInterface`
   * Bind new file log repo
7. **Docs**
   * Update/overwrite `docs/architecture/deadline_notifier.md`
8. **Tests**
   * Mock `TaskManagerRepositoryInterface` & `UserConfigInterface`
   * Ensure idempotency via the file log repo
9. **CI / Quality Gates**
   * PEP-8, Clean Architecture, ≥ 90 % coverage

## 📤 Meta-commands
/write-unit-tests
/write-integrated-tests
/generate-docs
