# Example Configuration Files

## Overview

This directory contains example configuration files for setting up the Metrics Tracking System. Copy these files to your project and customize them according to your environment.

## File Structure

```
config/
├── metrics_config.json.example          # Main configuration file
├── dev-service-account.json.example     # Development Google service account
├── staging-service-account.json.example # Staging Google service account
├── prod-service-account.json.example    # Production Google service account
└── environments/
    ├── dev.env.example                   # Development environment variables
    ├── staging.env.example               # Staging environment variables
    └── prod.env.example                  # Production environment variables
```

## Main Configuration

### metrics_config.json.example

```json
{
  "sheets": {
    "daily_scoreboard": {
      "sheet_id": "REPLACE_WITH_YOUR_DAILY_SHEET_ID",
      "range_template": "Daily_{month}_{year}!A:G",
      "headers": [
        "Developer Name",
        "Date",
        "Today Deadlines",
        "Resolved Tasks",
        "Logged Time",
        "Commits",
        "Comments"
      ],
      "auto_create_sheets": true,
      "sheet_name_pattern": "Daily_{month_name}_{year}"
    },
    "developer_metrics_matrix": {
      "sheet_id": "REPLACE_WITH_YOUR_SPRINT_SHEET_ID",
      "range_template": "Sprint_{sprint_id}!A:P",
      "headers": [
        "Developer Name",
        "All Tasks",
        "Completed Tasks",
        "Releases Related",
        "Stories Related",
        "Resolved Stories",
        "Resolved Bugs",
        "Delivery Delay",
        "Bug Delivery Delay",
        "Logged Time",
        "ETA All Tasks",
        "Support Epic Time",
        "Meeting Time",
        "Doc Merge Requests",
        "Merge Requests",
        "Successful Merges"
      ],
      "auto_create_sheets": true,
      "sheet_name_pattern": "Sprint_{sprint_name}"
    }
  },
  "developers": {
    "john.doe@company.com": {
      "display_name": "John Doe",
      "jira_username": "john.doe",
      "gitlab_username": "jdoe",
      "email": "john.doe@company.com",
      "team": "Backend Team",
      "active": true,
      "aliases": [
        "j.doe@company.com",
        "john@company.com"
      ]
    },
    "jane.smith@company.com": {
      "display_name": "Jane Smith",
      "jira_username": "jane.smith",
      "gitlab_username": "jsmith",
      "email": "jane.smith@company.com",
      "team": "Frontend Team",
      "active": true,
      "aliases": [
        "j.smith@company.com"
      ]
    },
    "bob.wilson@company.com": {
      "display_name": "Bob Wilson",
      "jira_username": "bob.wilson",
      "gitlab_username": "bwilson",
      "email": "bob.wilson@company.com",
      "team": "DevOps Team",
      "active": true,
      "aliases": []
    },
    "alice.brown@company.com": {
      "display_name": "Alice Brown",
      "jira_username": "alice.brown",
      "gitlab_username": "abrown",
      "email": "alice.brown@company.com",
      "team": "QA Team",
      "active": false,
      "aliases": [
        "a.brown@company.com"
      ]
    }
  },
  "projects": {
    "MAIN": {
      "name": "Main Application",
      "key": "MAIN",
      "gitlab_project_id": 123,
      "track_metrics": true,
      "team_lead": "john.doe@company.com",
      "sprint_prefix": "MAIN-Sprint",
      "default_sprint_duration_weeks": 2
    },
    "SUPPORT": {
      "name": "Customer Support",
      "key": "SUPPORT",
      "gitlab_project_id": 456,
      "track_metrics": false,
      "team_lead": "jane.smith@company.com",
      "sprint_prefix": "SUPPORT-Sprint",
      "default_sprint_duration_weeks": 1
    },
    "INFRA": {
      "name": "Infrastructure",
      "key": "INFRA",
      "gitlab_project_id": 789,
      "track_metrics": true,
      "team_lead": "bob.wilson@company.com",
      "sprint_prefix": "INFRA-Sprint",
      "default_sprint_duration_weeks": 3
    }
  },
  "settings": {
    "timezone": "Asia/Tehran",
    "persian_calendar": true,
    "auto_create_sheets": true,
    "retry_attempts": 5,
    "retry_backoff_seconds": 2,
    "idempotency_cache_ttl_hours": 24,
    "batch_update_size": 100,
    "max_processing_time_seconds": 30,
    "enable_detailed_logging": false,
    "calendar_settings": {
      "month_names": [
        "Farvardin", "Ordibehesht", "Khordad",
        "Tir", "Mordad", "Shahrivar",
        "Mehr", "Aban", "Azar",
        "Dey", "Bahman", "Esfand"
      ],
      "year_offset": 1403,
      "weekend_days": ["Friday"],
      "business_hours": {
        "start": "09:00",
        "end": "17:00"
      },
      "holidays": [
        "1403-01-01",
        "1403-01-02",
        "1403-01-03",
        "1403-01-13",
        "1403-06-15"
      ]
    },
    "sprint_detection": {
      "name_patterns": [
        "Sprint \\d+",
        "MAIN-Sprint-\\d+",
        "Release \\d+\\.\\d+"
      ],
      "custom_field_id": "customfield_10020",
      "auto_detect": true,
      "fallback_sprint_name": "Default Sprint"
    },
    "notification_settings": {
      "enable_error_notifications": true,
      "enable_success_notifications": false,
      "slack_webhook_url": "",
      "email_notifications": {
        "enabled": false,
        "smtp_server": "",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "from_email": "",
        "to_emails": []
      }
    }
  }
}
```

## Environment Configuration Files

### dev.env.example

```bash
# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# API Configuration
API_HOST=localhost
API_PORT=8000
API_DEBUG=true

# Google Sheets Configuration
GOOGLE_SERVICE_ACCOUNT_FILE=config/dev-service-account.json
DAILY_SCOREBOARD_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
SPRINT_MATRIX_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

# Webhook Secrets (use simple secrets for development)
JIRA_WEBHOOK_SECRET=dev_jira_secret_123
GITLAB_WEBHOOK_SECRET=dev_gitlab_secret_456

# Configuration File Path
METRICS_CONFIG_FILE=config/metrics_config.json

# Cache Configuration (optional for development)
# REDIS_URL=redis://localhost:6379/0

# Monitoring (optional for development)
# SENTRY_DSN=https://your-dev-sentry-dsn

# Testing Configuration
ENABLE_TEST_ENDPOINTS=true
MOCK_GOOGLE_SHEETS=false
```

### staging.env.example

```bash
# Environment
ENVIRONMENT=staging
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Google Sheets Configuration
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secrets/staging-service-account.json
DAILY_SCOREBOARD_SHEET_ID=REPLACE_WITH_STAGING_DAILY_SHEET_ID
SPRINT_MATRIX_SHEET_ID=REPLACE_WITH_STAGING_SPRINT_SHEET_ID

# Webhook Secrets
JIRA_WEBHOOK_SECRET=REPLACE_WITH_STAGING_JIRA_SECRET
GITLAB_WEBHOOK_SECRET=REPLACE_WITH_STAGING_GITLAB_SECRET

# Configuration File Path
METRICS_CONFIG_FILE=/app/config/metrics_config.json

# Cache Configuration
REDIS_URL=redis://redis:6379/0

# Monitoring
SENTRY_DSN=REPLACE_WITH_STAGING_SENTRY_DSN
PROMETHEUS_ENABLED=true

# Rate Limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60

# Security
CORS_ORIGINS=["https://staging.your-domain.com"]
TRUSTED_HOSTS=["staging.your-domain.com"]

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"  # Daily at 2 AM
```

### prod.env.example

```bash
# Environment
ENVIRONMENT=production
LOG_LEVEL=WARNING

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Google Sheets Configuration
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secrets/production-service-account.json
DAILY_SCOREBOARD_SHEET_ID=REPLACE_WITH_PRODUCTION_DAILY_SHEET_ID
SPRINT_MATRIX_SHEET_ID=REPLACE_WITH_PRODUCTION_SPRINT_SHEET_ID

# Webhook Secrets (use strong, unique secrets for production)
JIRA_WEBHOOK_SECRET=REPLACE_WITH_STRONG_JIRA_SECRET
GITLAB_WEBHOOK_SECRET=REPLACE_WITH_STRONG_GITLAB_SECRET

# Configuration File Path
METRICS_CONFIG_FILE=/app/config/metrics_config.json

# Cache Configuration
REDIS_URL=redis://redis-service:6379/0
REDIS_PASSWORD=REPLACE_WITH_REDIS_PASSWORD

# Database Configuration (for future use)
# DATABASE_URL=postgresql://user:password@db-host:5432/metrics_db

# Monitoring
SENTRY_DSN=REPLACE_WITH_PRODUCTION_SENTRY_DSN
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Rate Limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60
RATE_LIMIT_REDIS_URL=redis://redis-service:6379/1

# Security
CORS_ORIGINS=["https://metrics.your-domain.com"]
TRUSTED_HOSTS=["metrics.your-domain.com"]
ALLOWED_IPS=["192.168.1.0/24", "10.0.0.0/8"]  # Jira/GitLab server IPs

# SSL Configuration
SSL_CERT_PATH=/app/ssl/cert.pem
SSL_KEY_PATH=/app/ssl/key.pem

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"  # Daily at 2 AM
BACKUP_RETENTION_DAYS=30
BACKUP_S3_BUCKET=your-backup-bucket
BACKUP_S3_REGION=us-east-1

# Performance Tuning
WORKER_PROCESSES=4
WORKER_TIMEOUT=30
MAX_REQUESTS=1000
MAX_REQUESTS_JITTER=100

# Feature Flags
ENABLE_PERSIAN_CALENDAR=true
ENABLE_AUTO_SHEET_CREATION=true
ENABLE_BATCH_PROCESSING=true
ENABLE_WEBHOOK_REPLAY=true
```

## Google Service Account Examples

### dev-service-account.json.example

```json
{
  "type": "service_account",
  "project_id": "your-dev-project-id",
  "private_key_id": "dev-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nREPLACE_WITH_YOUR_DEV_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "metrics-dev@your-dev-project.iam.gserviceaccount.com",
  "client_id": "dev-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/metrics-dev%40your-dev-project.iam.gserviceaccount.com"
}
```

### staging-service-account.json.example

```json
{
  "type": "service_account",
  "project_id": "your-staging-project-id",
  "private_key_id": "staging-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nREPLACE_WITH_YOUR_STAGING_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "metrics-staging@your-staging-project.iam.gserviceaccount.com",
  "client_id": "staging-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/metrics-staging%40your-staging-project.iam.gserviceaccount.com"
}
```

### prod-service-account.json.example

```json
{
  "type": "service_account",
  "project_id": "your-production-project-id",
  "private_key_id": "production-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nREPLACE_WITH_YOUR_PRODUCTION_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "metrics-prod@your-production-project.iam.gserviceaccount.com",
  "client_id": "production-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/metrics-prod%40your-production-project.iam.gserviceaccount.com"
}
```

## Setup Instructions

### 1. Copy Configuration Files

```bash
# Copy main configuration
cp config/metrics_config.json.example config/metrics_config.json

# Copy environment files
cp config/environments/dev.env.example .env

# Copy service account files (after obtaining from Google Cloud)
cp config/dev-service-account.json.example config/dev-service-account.json
```

### 2. Customize Configuration

1. **Edit metrics_config.json:**
   - Replace sheet IDs with your actual Google Sheet IDs
   - Update developer information with your team members
   - Configure projects according to your Jira/GitLab setup
   - Adjust timezone and calendar settings

2. **Edit environment file (.env):**
   - Replace placeholder values with actual configurations
   - Set appropriate log levels for your environment
   - Configure webhook secrets (use strong secrets for production)
   - Set up monitoring URLs (Sentry, etc.)

3. **Configure service accounts:**
   - Download actual service account JSON files from Google Cloud Console
   - Replace example files with real credentials
   - Ensure service accounts have proper permissions

### 3. Validate Configuration

Use the validation script to check your configuration:

```bash
python scripts/validate_config.py config/metrics_config.json
```

### 4. Test Configuration

Run a test to verify everything is working:

```bash
# Test Google Sheets access
python scripts/test_sheets_access.py

# Test webhook endpoints
curl -X POST http://localhost:8000/metrics/health

# Test with sample webhook
python scripts/test_webhook.py
```

## Configuration Best Practices

### Security

1. **Never commit real credentials:** Use `.gitignore` to exclude real configuration files
2. **Use strong secrets:** Generate cryptographically strong webhook secrets
3. **Rotate credentials:** Regularly rotate service account keys and webhook secrets
4. **Limit permissions:** Give service accounts minimal required permissions

### Environment Separation

1. **Separate projects:** Use different Google Cloud projects for each environment
2. **Separate sheets:** Use different Google Sheets for each environment
3. **Different secrets:** Use different webhook secrets for each environment
4. **Isolated resources:** Keep development, staging, and production completely separate

### Maintenance

1. **Version control:** Keep configuration templates in version control
2. **Documentation:** Document any custom configuration changes
3. **Backup:** Regularly backup configuration files
4. **Review:** Regularly review and update configurations

### Performance

1. **Cache settings:** Configure appropriate cache TTL values
2. **Batch sizes:** Adjust batch sizes based on your load
3. **Retry logic:** Configure retry settings based on your reliability requirements
4. **Resource limits:** Set appropriate timeouts and limits

## Troubleshooting

### Common Issues

1. **Permission Denied:** Check service account permissions on Google Sheets
2. **Sheet Not Found:** Verify sheet IDs are correct and accessible
3. **Webhook Failures:** Check webhook secrets and endpoint URLs
4. **Developer Mapping:** Ensure developer emails match webhook payloads

### Debug Configuration

Enable debug mode for troubleshooting:

```json
{
  "settings": {
    "enable_detailed_logging": true,
    "log_webhook_payloads": true,
    "log_sheet_operations": true,
    "log_developer_mapping": true
  }
}
```

### Validation Scripts

Create custom validation scripts for your specific setup:

```python

"""Custom configuration validation."""

import json
import sys
from pathlib import Path

def validate_custom_config():
    """Validate organization-specific configuration."""
    # Add your custom validation logic here
    pass

if __name__ == "__main__":
    validate_custom_config()
```

This configuration guide provides comprehensive examples and instructions for setting up the Metrics Tracking System in any environment.
