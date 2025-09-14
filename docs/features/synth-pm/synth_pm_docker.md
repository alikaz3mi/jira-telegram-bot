# SynthPM Docker Service

## Overview
The `synth-pm` Docker service runs the SynthPM background synchronization service. This service periodically synchronizes data between Google Sheets ("pm Features"), Jira (PM Board project), and Telegram channels.

## Docker Service Configuration

The service is defined in `docker-compose.yml`:

```yaml
synth-pm:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: synth_pm
  image: jira_telegram_bot:v3
  volumes:
    - .:/app
  command: >
    python3 scripts/run_synth_pm.py service
  restart: always
  environment:
    - POSTGRES_HOST=postgres
    - POSTGRES_PORT=5432
```

## Running the Service

### Using Docker Compose
```bash
# Start the SynthPM service
docker-compose up synth-pm

# Start in background
docker-compose up -d synth-pm

# View logs
docker-compose logs -f synth-pm
```

### Manual Script Execution
```bash
# One-time synchronization
python3 scripts/run_synth_pm.py sync

# Background service (continuous)
python3 scripts/run_synth_pm.py service

# Test connections
python3 scripts/run_synth_pm.py test
```

## Features

### Bidirectional Synchronization
- **Google Sheets → Jira**: Creates/updates Jira tasks from pm features
- **Jira → Google Sheets**: Updates feature status and progress
- **Jira → Telegram**: Posts notifications when status changes to "۲"

### API Endpoints
The service also exposes REST API endpoints via the main application:
- `GET /synth-pm/features` - List all pm features
- `POST /synth-pm/sync` - Trigger manual synchronization
- `POST /synth-pm/webhook/jira` - Handle Jira webhooks

### Configuration
Configure via environment variables or settings files:
- **Google Sheets credentials**: Service account JSON file
- **Jira connection settings**: Domain, username, password/token
- **Telegram bot configuration**:
  - `SYNTH_pm_TELEGRAM_BOT_TOKEN`: Dedicated bot token for SynthPM
  - `SYNTH_pm_TELEGRAM_CHANNEL_ID`: Target channel for notifications
  - `SYNTH_pm_TELEGRAM_GROUP_ID`: Optional group for notifications
- **Synchronization intervals**: How often to check for changes

#### Telegram Bot Setup
1. Create a new bot using [@BotFather](https://t.me/botfather)
2. Get the bot token and set `SYNTH_pm_TELEGRAM_BOT_TOKEN`
3. Add the bot to your target channel/group
4. Make the bot an admin with permission to send messages
5. Get the channel/group ID and set `SYNTH_pm_TELEGRAM_CHANNEL_ID`

## Monitoring
- Check logs: `docker-compose logs synth-pm`
- Health checks via API endpoints
- Connection tests: `python3 scripts/run_synth_pm.py test`

## Dependencies
- Google Sheets API access
- Jira REST API access
- Telegram Bot API access
- All dependencies managed via the main application's dependency injection container
