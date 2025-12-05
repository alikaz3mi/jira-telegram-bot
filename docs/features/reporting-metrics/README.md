# Metrics Tracking System - README

## Overview

The Metrics Tracking System is a comprehensive solution for automatically collecting, processing, and visualizing development metrics from Jira and GitLab webhooks. It provides real-time updates to Google Sheets for tracking daily developer performance and sprint-level metrics, following Clean Architecture principles.

## Features

- **Real-time Metrics Collection**: Automatically capture development activities from Jira and GitLab webhooks
- **Daily Scoreboard**: Track daily developer metrics including tasks resolved, time logged, and commits
- **Sprint Metrics Matrix**: Comprehensive sprint-level performance tracking and analytics
- **Persian Calendar Support**: Native support for Persian calendar with automatic monthly sheet creation
- **Idempotent Processing**: Prevent duplicate metric entries with built-in idempotency checking
- **Resilient Architecture**: Automatic retry logic with exponential backoff for transient failures
- **Clean Architecture**: Strict separation of concerns with entities, use cases, adapters, and frameworks
- **Comprehensive Testing**: 90%+ test coverage with unit and integration tests

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Google Cloud service account with Sheets API access
- Jira instance with webhook configuration access
- GitLab project with webhook configuration access

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/your-org/jira-telegram-bot.git
cd jira-telegram-bot
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install -e .
```

3. **Configure the system:**
```bash
# Copy example configuration
cp config/metrics_config.json.example config/metrics_config.json
cp config/environments/dev.env.example .env

# Edit configuration files with your settings
nano config/metrics_config.json
nano .env
```

4. **Set up Google Sheets:**
   - Create Google service account and download JSON key
   - Create Google Sheets for daily scoreboard and sprint metrics
   - Share sheets with service account email (Editor permissions)
   - Update sheet IDs in configuration

5. **Run the application:**
```bash
python -m jira_telegram_bot.frameworks.fastapi.main
```

### Basic Configuration

Edit `config/metrics_config.json`:

```json
{
  "sheets": {
    "daily_scoreboard": {
      "sheet_id": "your_daily_sheet_id"
    },
    "developer_metrics_matrix": {
      "sheet_id": "your_sprint_sheet_id"
    }
  },
  "developers": {
    "john.doe@company.com": {
      "display_name": "John Doe",
      "jira_username": "john.doe",
      "gitlab_username": "jdoe",
      "team": "Backend Team",
      "active": true
    }
  },
  "settings": {
    "timezone": "Asia/Tehran",
    "persian_calendar": true
  }
}
```

## Architecture

The system follows Clean Architecture principles with clear separation of layers:

```
├── entities/metrics/           # Domain models (MetricEvent, DailyMetricRow, etc.)
├── use_cases/metrics/          # Business logic (ProcessJiraEvent, UpdateSheet, etc.)
├── adapters/                   # External integrations (GoogleSheetsGateway, etc.)
└── frameworks/fastapi/         # Web framework (webhook endpoints)
```

### Key Components

- **MetricEvent**: Core entity representing trackable development activities
- **ProcessJiraEventUseCase**: Maps Jira webhooks to metric events
- **ProcessGitlabEventUseCase**: Maps GitLab webhooks to metric events
- **UpdateSheetUseCase**: Updates Google Sheets with metric data
- **GoogleSheetsGateway**: Handles Google Sheets API operations
- **MetricsWebhookEndpoint**: FastAPI endpoints for webhook ingestion

## Supported Metrics

### Daily Scoreboard Metrics
- Today's deadlines count
- Tasks resolved today
- Hours logged today
- Commits made today
- Latest work comments

### Sprint Metrics Matrix
- Total assigned tasks
- Completed tasks
- Resolved stories and bugs
- Time logged
- Merge requests opened/merged
- Delivery delays
- Support and meeting time

### Supported Events
- **Jira**: Issue created/updated/resolved, worklog entries
- **GitLab**: Push events (commits), merge request events

## API Endpoints

### Webhook Endpoints
- `POST /metrics/jira` - Process Jira webhook events
- `POST /metrics/gitlab` - Process GitLab webhook events

### Monitoring Endpoints
- `GET /metrics/health` - System health check
- `GET /metrics/stats` - Detailed metrics and statistics
- `GET /metrics/errors` - Recent processing errors

### Example Webhook Usage

```bash
# Send Jira webhook
curl -X POST https://your-domain.com/metrics/jira \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your_secret" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "issue": {
      "key": "PROJ-123",
      "fields": {
        "assignee": {"emailAddress": "john.doe@company.com"},
        "summary": "New task"
      }
    }
  }'
```

## Configuration

### Environment Variables

```bash
# Google Sheets
GOOGLE_SERVICE_ACCOUNT_FILE=config/service-account.json
DAILY_SCOREBOARD_SHEET_ID=your_daily_sheet_id
SPRINT_MATRIX_SHEET_ID=your_sprint_sheet_id

# Webhook Authentication
JIRA_WEBHOOK_SECRET=your_jira_secret
GITLAB_WEBHOOK_SECRET=your_gitlab_secret

# Application Settings
METRICS_CONFIG_FILE=config/metrics_config.json
LOG_LEVEL=INFO
```

### Webhook Configuration

#### Jira Webhook Setup
1. Go to Jira Administration → System → Webhooks
2. Create webhook with URL: `https://your-domain.com/metrics/jira`
3. Select events: Issue Created, Updated, Resolved, Worklog
4. Add secret header: `X-Webhook-Secret: your_secret`

#### GitLab Webhook Setup
1. Go to Project → Settings → Webhooks
2. Add URL: `https://your-domain.com/metrics/gitlab`
3. Select triggers: Push events, Merge request events
4. Add secret token: `your_secret`

## Deployment

### Docker Deployment

```bash
# Build image
docker build -t metrics-api .

# Run container
docker run -d \
  --name metrics-api \
  -p 8000:8000 \
  -v ./config:/app/config:ro \
  -v ./logs:/app/logs \
  --env-file .env \
  metrics-api
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrics-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: metrics-api
  template:
    spec:
      containers:
      - name: metrics-api
        image: your-registry/metrics-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: GOOGLE_SERVICE_ACCOUNT_FILE
          value: "/app/secrets/service-account.json"
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        - name: secrets-volume
          mountPath: /app/secrets
      volumes:
      - name: config-volume
        configMap:
          name: metrics-config
      - name: secrets-volume
        secret:
          secretName: metrics-secrets
```

## Testing

### Running Tests

```bash
# Unit tests
python -m pytest tests/unit_tests/use_cases/metrics/ -v

# Integration tests
python -m pytest tests/integration/metrics/ -v

# Coverage report
python -m pytest tests/unit_tests/use_cases/metrics/ --cov=jira_telegram_bot.use_cases.metrics --cov-report=html
```

### Test Structure

```
tests/
├── unit_tests/use_cases/metrics/        # Unit tests for business logic
├── integration/metrics/                 # Integration tests
└── samples/                            # Test data and fixtures
```

## Monitoring

### Health Checks

```bash
# Basic health check
curl https://your-domain.com/metrics/health

# Detailed health with metrics
curl https://your-domain.com/metrics/health?detailed=true
```

### Metrics and Observability

- **Prometheus metrics**: Request rates, processing times, error rates
- **Structured logging**: JSON logs with correlation IDs
- **Sentry integration**: Error tracking and performance monitoring
- **Health endpoints**: Service dependency monitoring

## Security

### Webhook Security
- HTTPS endpoints required
- Webhook signature verification
- Rate limiting (1000 requests/minute)
- IP whitelisting support

### Data Protection
- Google service account authentication
- Minimal required permissions
- Secret management via environment variables
- No sensitive data in logs

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check Google service account has Editor access to sheets
2. **Developer Not Found**: Verify developer email mapping in configuration
3. **Webhook Failures**: Check webhook secrets and endpoint accessibility
4. **Sheet Updates Failing**: Verify sheet IDs and format

### Debug Mode

Enable detailed logging:

```bash
LOG_LEVEL=DEBUG python -m jira_telegram_bot.frameworks.fastapi.main
```

### Support

- **Documentation**: [docs/metrics/](docs/metrics/)
- **Configuration Guide**: [docs/metrics/configuration_guide.md](docs/metrics/configuration_guide.md)
- **API Documentation**: [docs/metrics/api_documentation.md](docs/metrics/api_documentation.md)
- **Deployment Guide**: [docs/metrics/deployment_guide.md](docs/metrics/deployment_guide.md)

## Development

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/metrics-enhancement`
3. Make changes following Clean Architecture principles
4. Add tests with 90%+ coverage
5. Run linting: `ruff check` and `mypy --strict`
6. Submit pull request

### Code Standards

- **Clean Architecture**: Strict layer separation
- **Type Hints**: Full type annotation required
- **Testing**: 90%+ coverage with unit and integration tests
- **Documentation**: Comprehensive docstrings and API docs
- **Linting**: `ruff` and `mypy --strict` compliance

### Project Structure

```
jira_telegram_bot/
├── entities/metrics/                    # Domain models
│   ├── constants.py                     # Enums and constants
│   ├── metric_event.py                  # Core metric event entity
│   ├── daily_metric_row.py              # Daily scoreboard row
│   └── sprint_metric_row.py             # Sprint matrix row
├── use_cases/
│   ├── interfaces/metrics/              # Interface contracts
│   └── metrics/                         # Business logic
│       ├── process_jira_event_use_case.py
│       ├── process_gitlab_event_use_case.py
│       └── update_sheet_use_case.py
├── adapters/
│   ├── gateways/google_sheets/          # Google Sheets integration
│   ├── repositories/                    # Configuration storage
│   └── services/metrics/                # Metrics processing
└── frameworks/fastapi/webhooks/metrics/ # FastAPI endpoints
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

## Changelog

### v1.0.0 (Latest)
- Initial release with complete metrics tracking system
- Daily scoreboard and sprint metrics matrix
- Jira and GitLab webhook integration
- Persian calendar support
- Comprehensive test coverage
- Clean Architecture implementation
- Docker and Kubernetes deployment support

## Roadmap

### Upcoming Features
- **v1.1.0**: Advanced analytics and trend analysis
- **v1.2.0**: Web dashboard for metric visualization
- **v1.3.0**: Slack/Teams integration for notifications
- **v1.4.0**: Custom metric definitions and formulas
- **v1.5.0**: Historical data migration and reporting

For detailed roadmap and feature requests, see [GitHub Issues](https://github.com/your-org/jira-telegram-bot/issues).
