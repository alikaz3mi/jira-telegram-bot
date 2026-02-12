# Jira Telegram Bot

<p align="center">
   <img src="docs/image.png" alt="Jira Telegram Bot" width="50%">
</p>

A production-grade Telegram bot that integrates with Jira to streamline project management through chat. Built with **Clean Architecture**, it supports AI-powered task creation, voice commands, deadline notifications, Google Sheets synchronization, sprint analytics, and more.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Scripts](#scripts)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

### Task Management
- **Interactive Task Creation** — guided conversations to create Jira issues
- **Advanced Task Creation** — AI-powered breakdown of complex projects into multiple stories
- **Voice Commands** — speech-to-text transcription for task descriptions
- **Task Transitions** — change issue status directly from Telegram
- **Media Support** — attach images, documents, videos, and audio to tasks
- **Webhook Integration** — bidirectional sync between Jira and Telegram (comments, status changes, assignments)

### Smart Features
- **AI Integration** — OpenAI (GPT) and Google Gemini for task analysis, user-story generation, and daily reports
- **Voice Processing** — automatic transcription of voice messages into actionable tasks
- **Smart Notifications** — configurable deadline alerts and status-change notifications
- **Multilingual Support** — handles English and Persian text (including Jalali calendar)

### Data Synchronization
- **Google Sheets Sync** — synchronize stories, bugs, and improvements to spreadsheets
- **PostgreSQL Warehouse** — full Jira issue sync to a relational database for analytics
- **GitLab Commit Tracking** — fetch and store commit data for developer metrics

### Sprint & Team Analytics
- **Sprint Reports** — completion rates, status breakdowns, and workload heat-maps
- **Team Evaluation** — sprint-close metrics written to Google Sheets
- **Developer Metrics** — PR counts, commit stats, and productivity dashboards

### Team Collaboration
- **User Assignment** — smart assignee suggestions based on component ownership
- **Group Chat Support** — create and manage tasks from group conversations
- **Channel Forwarding** — forward channel posts as Jira tickets automatically
- **Role-Based Access** — board-level admin/user roles and allowed-user lists

---

## Architecture

The project follows **Clean Architecture** with strict dependency rules:

```
entities/          Pure business objects (Pydantic models)
use_cases/         Application logic & interfaces
adapters/          Repositories, AI models, services
frameworks/        Telegram bot, FastAPI, CLI, schedulers
settings/          Pydantic Settings (loaded from .env)
```

Dependency injection is handled by **Lagom**. Bindings are declared in `config_dependency_injection.py` and the container is created in `app_container.py`.

---

## Setup

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Required |
| Telegram Bot Token | From [@BotFather](https://t.me/botfather) |
| Jira Server/Cloud | With API access |
| PostgreSQL 15+ | For data warehouse (optional) |
| OpenAI / Gemini API key | For AI features (optional) |
| Google Sheets credentials | For sheet synchronization (optional) |

### Installation

```bash
git clone https://github.com/your-org/jira-telegram-bot.git
cd jira-telegram-bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e .
```

### Environment Configuration

Copy the sample environment file and fill in required values:

```bash
cp sample.env .env
```

**Required variables:**

```env
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_HOOK_TOKEN=your_webhook_secret
JIRA_DOMAIN=https://your-jira-instance.com
JIRA_USERNAME=your_username
JIRA_PASSWORD=your_api_token
```

**Optional variables (enable extra features):**

```env
# AI features
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# PostgreSQL data warehouse
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=jira_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret

# Google Sheets sync
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json

# GitLab commit tracking
GITLAB_URL=https://gitlab.example.com
GITLAB_ACCESS_TOKEN=glpat-...
GITLAB_PROJECT_NAME_FILTERS=["myproject","auth"]

# Jira sync
SYNC_PROJECT_KEYS=["PROJ1","PROJ2"]
PM_PROJECT_KEY=PM

# Deadline notifications
DEADLINE_NOTIFIER_GROUP_CHAT_ID=-1001234567890
GROUP_NOTIFICATION_USERNAMES=["user1","user2"]
```

### Run the Bot

```bash
python -m jira_telegram_bot
```

### Docker Deployment

```bash
docker-compose up -d
```

For PostgreSQL with pgAdmin:
```bash
cd docker && docker-compose up -d
```

---

## Configuration

### Jira Custom Fields

Map your Jira instance's custom field IDs:

```env
JIRA_EPIC_LINK_ID=customfield_10100
JIRA_SPRINT_ID=customfield_10104
JIRA_STORY_POINTS_ID=customfield_10106
```

### User Configuration

Users are managed through `UserConfig` (file-based or MongoDB-backed). Each user can have:

- Telegram username ↔ Jira username mapping
- Default project and board assignments
- Component preferences
- Board-level roles (`admin` / `user` / `superadmin`)
- Notification preferences

### Board Configuration

Project boards are configured in `settings/projects_info.json` or via environment variables, defining:

- Project keys and display names
- Available components and assignees
- Sprint and epic mappings

---

## Usage

### Telegram Commands

| Command | Description |
|---|---|
| `/create_task` | Create a new Jira issue (supports recursive creation) |
| `/advanced_task` | AI-powered multi-task creation from text or voice |
| `/transition` | Change an issue's workflow status |
| `/status` | Check issue status |
| `/summary_tasks` | Get a board summary |
| `/setting` | Configure user preferences |
| `/help` | Show available commands |

### Creating Tasks

1. Send `/create_task`
2. Select a project board
3. Enter summary and description
4. Choose component(s), assignee, priority, sprint, and epic
5. Attach media files (optional)
6. Confirm — then optionally create another task

### Advanced Task Creation (AI)

1. Send `/advanced_task`
2. Select a project
3. Provide requirements via text or voice message
4. Review the AI-generated task breakdown
5. Confirm to create all tasks at once

### Webhook Integration

The bot exposes FastAPI endpoints for Jira webhooks:

- **Issue events** — comment added, status changed, assignee updated
- **Sprint events** — sprint closed triggers team evaluation
- **Channel posts** — Telegram channel messages auto-create Jira tickets

---

## Scripts

Utility scripts are located in `scripts/`:

| Script | Purpose |
|---|---|
| `run_deadline_notifier.py` | Cron-driven deadline alert service |
| `sync_stories.py` | Sync Jira stories to Google Sheets |
| `sync_bugs_improvements.py` | Sync bugs/improvements to Sheets |
| `team_evaluation_cli.py` | CLI for sprint-close team evaluation |
| `backfill_actual_dates.py` | Backfill calculated actual dates |
| `generate_reports_once.py` | One-shot Jira report generation |

See [docs/SCRIPTS_ORGANIZATION.md](docs/SCRIPTS_ORGANIZATION.md) for the full list.

---

## Testing

### Unit Tests

```bash
make unit-tests
```

### Integration Tests

Integration tests run against a real Jira instance:

```bash
export JIRA_DOMAIN=https://your-jira-instance.com
export JIRA_USERNAME=your_username
export JIRA_PASSWORD=your_password
export JIRA_TEST_PROJECT_KEY=TEST

make integration-tests
```

### Coverage

```bash
make unit-tests    # generates reports/coverage_html/index.html
```

Tests follow **Arrange–Act–Assert**, use `unittest` exclusively, and target ≥ 90% line coverage.

---

## Documentation

| Document | Description |
|---|---|
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/features/](docs/features/) | Feature-specific guides |
| [docs/database-sync-guide.md](docs/database-sync-guide.md) | PostgreSQL sync setup |
| [docs/SCRIPTS_ORGANIZATION.md](docs/SCRIPTS_ORGANIZATION.md) | Scripts reference |
| [docs/LARGE_FILE_UPLOAD_GUIDE.md](docs/LARGE_FILE_UPLOAD_GUIDE.md) | Media upload guide |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Follow the coding conventions in [.github/copilot-instructions.md](.github/copilot-instructions.md)
4. Write tests (≥ 90% coverage)
5. Submit a pull request

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

## Credits

- [python-telegram-bot](https://python-telegram-bot.org/)
- [jira-python](https://jira.readthedocs.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Lagom](https://lagom-di.readthedocs.io/) (dependency injection)
- [Pydantic](https://docs.pydantic.dev/) (settings & validation)
- AI features powered by [OpenAI](https://openai.com/) and [Google Gemini](https://deepmind.google/technologies/gemini/)