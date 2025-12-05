# Configuration Guide

## Overview

The Metrics Tracking System requires proper configuration for Google Sheets integration, developer mappings, and webhook authentication. This guide covers all configuration aspects.

## Configuration Files

### metrics_config.json

Main configuration file located in the project root:

```json
{
  "sheets": {
    "daily_scoreboard": {
      "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
      "range_template": "Daily_{month}_{year}!A:G",
      "headers": [
        "Developer Name",
        "Date",
        "Today Deadlines",
        "Resolved Tasks",
        "Logged Time",
        "Commits",
        "Comments"
      ]
    },
    "developer_metrics_matrix": {
      "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
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
      ]
    }
  },
  "developers": {
    "john.doe@company.com": {
      "display_name": "John Doe",
      "jira_username": "john.doe",
      "gitlab_username": "jdoe",
      "email": "john.doe@company.com",
      "team": "Backend",
      "active": true
    },
    "jane.smith@company.com": {
      "display_name": "Jane Smith",
      "jira_username": "jane.smith",
      "gitlab_username": "jsmith",
      "email": "jane.smith@company.com",
      "team": "Frontend",
      "active": true
    },
    "bob.wilson@company.com": {
      "display_name": "Bob Wilson",
      "jira_username": "bob.wilson",
      "gitlab_username": "bwilson",
      "email": "bob.wilson@company.com",
      "team": "DevOps",
      "active": false
    }
  },
  "projects": {
    "PROJ1": {
      "name": "Main Project",
      "key": "PROJ1",
      "gitlab_project_id": 123,
      "track_metrics": true
    },
    "SUPPORT": {
      "name": "Support Project",
      "key": "SUPPORT",
      "gitlab_project_id": 456,
      "track_metrics": false
    }
  },
  "settings": {
    "timezone": "Asia/Tehran",
    "persian_calendar": true,
    "auto_create_sheets": true,
    "retry_attempts": 5,
    "retry_backoff_seconds": 2,
    "idempotency_cache_ttl_hours": 24,
    "batch_update_size": 100
  }
}
```

## Environment Variables

### Required Variables

```bash
# Google Sheets Authentication
GOOGLE_SERVICE_ACCOUNT_FILE=config/service-account.json

# Sheet Configuration (alternative to config file)
DAILY_SCOREBOARD_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
SPRINT_MATRIX_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

# Webhook Authentication
JIRA_WEBHOOK_SECRET=your_jira_webhook_secret
GITLAB_WEBHOOK_SECRET=your_gitlab_webhook_secret

# Application Settings
METRICS_CONFIG_FILE=config/metrics_config.json
LOG_LEVEL=INFO
```

### Optional Variables

```bash
# Redis Configuration (for production)
REDIS_URL=redis://localhost:6379/0

# Database Configuration (for production)
DATABASE_URL=postgresql://user:pass@localhost/metrics_db

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
PROMETHEUS_ENABLED=true
```

## Google Sheets Setup

### Step 1: Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing one
3. Enable Google Sheets API
4. Go to IAM & Admin → Service Accounts
5. Create new service account:
   - Name: `metrics-tracker-service`
   - Description: `Service account for metrics tracking system`
6. Create and download JSON key file
7. Store securely and reference in `GOOGLE_SERVICE_ACCOUNT_FILE`

### Step 2: Create Google Sheets

#### Daily Scoreboard Sheet

1. Create new Google Sheet named "Daily Metrics Dashboard"
2. Create sheet tabs for each Persian month:
   - `Daily_1_1403` (Farvardin 1403)
   - `Daily_2_1403` (Ordibehesht 1403)
   - etc.
3. Set up headers in row 1:
   ```
   A: Developer Name
   B: Date
   C: Today Deadlines
   D: Resolved Tasks
   E: Logged Time
   F: Commits
   G: Comments
   ```
4. Share sheet with service account email (Editor permissions)
5. Copy sheet ID from URL

#### Sprint Metrics Matrix Sheet

1. Create new Google Sheet named "Sprint Metrics Matrix"
2. Create sheet tabs for each sprint:
   - `Sprint_1`
   - `Sprint_2`
   - etc.
3. Set up headers in row 1:
   ```
   A: Developer Name
   B: All Tasks
   C: Completed Tasks
   D: Releases Related
   E: Stories Related
   F: Resolved Stories
   G: Resolved Bugs
   H: Delivery Delay
   I: Bug Delivery Delay
   J: Logged Time
   K: ETA All Tasks
   L: Support Epic Time
   M: Meeting Time
   N: Doc Merge Requests
   O: Merge Requests
   P: Successful Merges
   ```
4. Share sheet with service account email (Editor permissions)
5. Copy sheet ID from URL

### Step 3: Configure Permissions

Ensure the service account has:
- **Editor** access to both sheets
- **Viewer** access to containing folders (if applicable)

## Developer Mapping Configuration

### Automatic Detection

The system attempts to automatically map developers using:

1. **Email matching**: Primary method using webhook email fields
2. **Username matching**: Fallback using Jira/GitLab usernames
3. **Display name matching**: Last resort using display names

### Manual Configuration

For precise control, configure each developer explicitly:

```json
{
  "developers": {
    "primary_email@company.com": {
      "display_name": "Developer Display Name",
      "jira_username": "jira.username",
      "gitlab_username": "gitlab_username",
      "email": "primary_email@company.com",
      "team": "Team Name",
      "active": true,
      "aliases": [
        "alternate@company.com",
        "old.email@company.com"
      ]
    }
  }
}
```

### Configuration Fields

- **display_name**: Name shown in sheets and reports
- **jira_username**: Jira account username/key
- **gitlab_username**: GitLab account username
- **email**: Primary email address
- **team**: Team/department assignment
- **active**: Whether to track metrics for this developer
- **aliases**: Alternative email addresses that map to this developer

## Webhook Configuration

### Jira Webhook Setup

1. Navigate to Jira Administration → System → Webhooks
2. Click "Create a Webhook"
3. Configure webhook:
   ```
   Name: Metrics Tracker
   Status: Enabled
   URL: https://your-domain.com/metrics/jira

   Events:
   ✓ Issue → created
   ✓ Issue → updated
   ✓ Issue → deleted
   ✓ Worklog → created
   ✓ Worklog → updated
   ✓ Worklog → deleted

   Filters:
   - Project = YOUR_PROJECT_KEY
   ```
4. Add secret token in headers (optional but recommended):
   ```
   X-Webhook-Secret: your_jira_webhook_secret
   ```

### GitLab Webhook Setup

1. Navigate to Project → Settings → Webhooks
2. Configure webhook:
   ```
   URL: https://your-domain.com/metrics/gitlab
   Secret Token: your_gitlab_webhook_secret

   Trigger Events:
   ✓ Push events
   ✓ Merge request events
   ✓ Pipeline events (optional)

   SSL verification: ✓ Enable
   ```

### Webhook Security

For production deployments, implement webhook verification:

```python
# Example verification in your endpoint
import hmac
import hashlib

def verify_jira_webhook(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

## Project Configuration

### Project Mapping

Configure which projects to track:

```json
{
  "projects": {
    "MAIN": {
      "name": "Main Application",
      "key": "MAIN",
      "gitlab_project_id": 123,
      "track_metrics": true,
      "team_lead": "john.doe@company.com",
      "sprint_prefix": "MAIN-Sprint"
    },
    "SUPPORT": {
      "name": "Customer Support",
      "key": "SUPPORT",
      "gitlab_project_id": 456,
      "track_metrics": false,
      "team_lead": "jane.smith@company.com"
    }
  }
}
```

### Sprint Configuration

Configure sprint tracking patterns:

```json
{
  "settings": {
    "sprint_detection": {
      "name_patterns": [
        "Sprint \\d+",
        "MAIN Sprint \\d+",
        "Release \\d+\\.\\d+"
      ],
      "custom_field_id": "customfield_10020",
      "auto_detect": true
    }
  }
}
```

## Time Zone and Calendar Configuration

### Persian Calendar Support

```json
{
  "settings": {
    "timezone": "Asia/Tehran",
    "persian_calendar": true,
    "calendar_settings": {
      "month_names": [
        "Farvardin", "Ordibehesht", "Khordad",
        "Tir", "Mordad", "Shahrivar",
        "Mehr", "Aban", "Azar",
        "Dey", "Bahman", "Esfand"
      ],
      "year_offset": 1403,
      "weekend_days": ["Friday"],
      "holidays": [
        "1403-01-01",
        "1403-01-02",
        "1403-01-03",
        "1403-01-13"
      ]
    }
  }
}
```

### Gregorian Calendar

```json
{
  "settings": {
    "timezone": "UTC",
    "persian_calendar": false,
    "calendar_settings": {
      "weekend_days": ["Saturday", "Sunday"],
      "business_hours": {
        "start": "09:00",
        "end": "17:00"
      }
    }
  }
}
```

## Advanced Configuration

### Retry and Error Handling

```json
{
  "settings": {
    "retry_settings": {
      "max_attempts": 5,
      "backoff_seconds": 2,
      "max_backoff_seconds": 60,
      "exponential_backoff": true,
      "retryable_errors": [
        "TransientGoogleError",
        "NetworkError",
        "RateLimitError"
      ]
    }
  }
}
```

### Caching Configuration

```json
{
  "settings": {
    "cache_settings": {
      "idempotency_ttl_hours": 24,
      "configuration_ttl_minutes": 30,
      "sheet_metadata_ttl_minutes": 15,
      "developer_mapping_ttl_hours": 1
    }
  }
}
```

### Batch Processing

```json
{
  "settings": {
    "batch_settings": {
      "batch_size": 100,
      "batch_timeout_seconds": 30,
      "enable_batching": true,
      "batch_flush_interval_seconds": 10
    }
  }
}
```

## Configuration Validation

### Validation Script

Create a validation script to verify configuration:

```python

"""Configuration validation script."""

import json
import sys
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

def validate_config(config_path: str) -> bool:
    """Validate metrics configuration file."""
    try:
        with open(config_path) as f:
            config = json.load(f)

        # Validate required sections
        required_sections = ['sheets', 'developers', 'settings']
        for section in required_sections:
            if section not in config:
                print(f"❌ Missing required section: {section}")
                return False

        # Validate sheet configuration
        for sheet_name, sheet_config in config['sheets'].items():
            if 'sheet_id' not in sheet_config:
                print(f"❌ Missing sheet_id for {sheet_name}")
                return False

        # Validate developer configuration
        for email, dev_config in config['developers'].items():
            required_fields = ['display_name', 'jira_username', 'gitlab_username']
            for field in required_fields:
                if field not in dev_config:
                    print(f"❌ Missing {field} for developer {email}")
                    return False

        print("✅ Configuration file is valid")
        return True

    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def validate_google_sheets_access(service_account_file: str, sheet_ids: list) -> bool:
    """Validate Google Sheets API access."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )

        service = build('sheets', 'v4', credentials=credentials)

        for sheet_id in sheet_ids:
            # Try to read sheet metadata
            sheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            print(f"✅ Successfully accessed sheet: {sheet['properties']['title']}")

        return True

    except Exception as e:
        print(f"❌ Google Sheets access validation failed: {e}")
        return False

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "metrics_config.json"

    if not validate_config(config_path):
        sys.exit(1)

    # Additional validations can be added here
    print("🎉 All validations passed!")
```

### Usage

```bash
python validate_config.py metrics_config.json
```

## Troubleshooting

### Common Configuration Issues

1. **Service Account Permission Denied**
   - Verify service account email has Editor access to sheets
   - Check that Google Sheets API is enabled
   - Ensure service account file path is correct

2. **Developer Mapping Not Working**
   - Check email addresses match webhook payloads exactly
   - Verify Jira/GitLab usernames are correct
   - Enable debug logging to see mapping attempts

3. **Sheet Updates Failing**
   - Verify sheet IDs are correct
   - Check sheet tab names match configuration
   - Ensure headers match expected format

4. **Webhook Events Not Processing**
   - Verify webhook URLs are accessible
   - Check webhook secret tokens match
   - Review webhook event selection in Jira/GitLab

5. **Time Zone Issues**
   - Ensure timezone setting matches your location
   - Verify Persian calendar configuration if applicable
   - Check that timestamps in sheets are correct

### Debug Configuration

Enable detailed logging for troubleshooting:

```json
{
  "settings": {
    "debug": {
      "enabled": true,
      "log_level": "DEBUG",
      "log_webhook_payloads": true,
      "log_sheet_operations": true,
      "log_developer_mapping": true
    }
  }
}
```

This will provide detailed logs for diagnosing configuration issues.
