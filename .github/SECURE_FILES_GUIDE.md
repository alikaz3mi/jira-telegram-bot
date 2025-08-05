# Secure Files Management for GitHub Actions

This guide explains how to securely handle sensitive files and credentials in GitHub Actions for the Jira Telegram Bot project.

## Overview

GitHub Actions provides several mechanisms to handle sensitive data:
1. **Repository Secrets**: For API keys, tokens, and small text values
2. **Environment Variables**: For configuration values
3. **Artifact Storage**: For files needed across jobs
4. **Base64 Encoding**: For binary files and certificates

## Setting Up Repository Secrets

### 1. Access Repository Settings
1. Go to your repository on GitHub
2. Click on `Settings` tab
3. Navigate to `Secrets and variables` > `Actions`

### 2. Add Required Secrets

#### Essential Application Secrets

**GOOGLE_CREDENTIALS**
```bash
# Base64 encode your Google service account JSON file
base64 -i google_service_account.json | pbcopy  # macOS
base64 -w 0 google_service_account.json         # Linux

# Add the output as GOOGLE_CREDENTIALS secret
```

**JIRA_PRIVATE_KEY**
```bash
# Base64 encode your JIRA private key file
base64 -i jira_private_key.pem | pbcopy  # macOS
base64 -w 0 jira_private_key.pem         # Linux

# Add the output as JIRA_PRIVATE_KEY secret
```

**TELEGRAM_BOT_TOKEN**
```
# Your Telegram bot token from @BotFather
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

**TELEGRAM_CHAT_ID**
```
# Your Telegram chat ID for notifications
-1001234567890
```

#### Docker Hub Secrets

**DOCKER_USERNAME**
```
your_dockerhub_username
```

**DOCKER_PASSWORD**
```
# Use Docker Hub access token (recommended) or password
dckr_pat_1234567890abcdef
```

#### Database Secrets (for production)

**DATABASE_URL**
```
postgresql://username:password@hostname:5432/database_name
```

**JIRA_SERVER_URL**
```
https://your-company.atlassian.net
```

## Environment-Specific Configuration

### Development Environment
```yaml
environment: development
secrets:
  - TELEGRAM_BOT_TOKEN_DEV
  - JIRA_SERVER_URL_DEV
  - DATABASE_URL_DEV
```

### Production Environment
```yaml
environment: production
secrets:
  - TELEGRAM_BOT_TOKEN_PROD
  - JIRA_SERVER_URL_PROD
  - DATABASE_URL_PROD
protection_rules:
  required_reviewers: 1
  wait_timer: 5
```

## Secure File Handling Patterns

### 1. JSON Configuration Files
```yaml
- name: Setup Google Credentials
  env:
    GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
  run: |
    mkdir -p data/storage
    echo "$GOOGLE_CREDENTIALS" | base64 -d > data/storage/google_credentials.json
    chmod 600 data/storage/google_credentials.json
```

### 2. Certificate and Key Files
```yaml
- name: Setup JIRA Private Key
  env:
    JIRA_PRIVATE_KEY: ${{ secrets.JIRA_PRIVATE_KEY }}
  run: |
    mkdir -p data/storage
    echo "$JIRA_PRIVATE_KEY" | base64 -d > data/storage/jira_private_key.pem
    chmod 600 data/storage/jira_private_key.pem
```

### 3. Environment Configuration
```yaml
- name: Setup environment variables
  run: |
    echo "DATABASE_URL=${{ secrets.DATABASE_URL }}" >> $GITHUB_ENV
    echo "TELEGRAM_BOT_TOKEN=${{ secrets.TELEGRAM_BOT_TOKEN }}" >> $GITHUB_ENV
    echo "JIRA_SERVER_URL=${{ secrets.JIRA_SERVER_URL }}" >> $GITHUB_ENV
```

## Security Best Practices

### 1. Principle of Least Privilege
- Only grant access to secrets that are needed for specific jobs
- Use environment-specific secrets for different deployment stages
- Rotate secrets regularly

### 2. Secret Validation
```yaml
- name: Validate required secrets
  run: |
    if [ -z "${{ secrets.TELEGRAM_BOT_TOKEN }}" ]; then
      echo "ERROR: TELEGRAM_BOT_TOKEN secret is not set"
      exit 1
    fi
    if [ -z "${{ secrets.GOOGLE_CREDENTIALS }}" ]; then
      echo "ERROR: GOOGLE_CREDENTIALS secret is not set"
      exit 1
    fi
```

### 3. Conditional Secret Usage
```yaml
- name: Setup optional secure files
  env:
    GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
    JIRA_PRIVATE_KEY: ${{ secrets.JIRA_PRIVATE_KEY }}
  run: |
    if [ ! -z "$GOOGLE_CREDENTIALS" ]; then
      echo "$GOOGLE_CREDENTIALS" | base64 -d > data/storage/google_credentials.json
      echo "✅ Google credentials configured"
    else
      echo "⚠️ Google credentials not available - skipping Google Sheets integration"
    fi
    
    if [ ! -z "$JIRA_PRIVATE_KEY" ]; then
      echo "$JIRA_PRIVATE_KEY" | base64 -d > data/storage/jira_private_key.pem
      echo "✅ JIRA private key configured"
    else
      echo "⚠️ JIRA private key not available - using token authentication"
    fi
```

## File Structure in CI

Your secure files will be available in the following locations during CI runs:

```
/github/workspace/
├── data/
│   └── storage/
│       ├── google_credentials.json      # From GOOGLE_CREDENTIALS secret
│       ├── jira_private_key.pem        # From JIRA_PRIVATE_KEY secret
│       └── other_config_files...
├── jira_telegram_bot/
└── tests/
```

## Testing with Secure Files

### 1. Mock Files for Testing
```yaml
- name: Create mock secure files for testing
  run: |
    mkdir -p data/storage
    echo '{"type": "service_account", "project_id": "test"}' > data/storage/google_credentials.json
    echo "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----" > data/storage/jira_private_key.pem
```

### 2. Conditional Testing
```python
import os
import pytest

@pytest.mark.skipif(
    not os.path.exists('data/storage/google_credentials.json'),
    reason="Google credentials not available"
)
def test_google_sheets_integration():
    # Test with real Google Sheets API
    pass

def test_google_sheets_mock():
    # Test with mocked Google Sheets API
    pass
```

## Troubleshooting

### Common Issues

1. **Base64 encoding issues**
   ```bash
   # Make sure to use -w 0 on Linux to avoid line wrapping
   base64 -w 0 file.json
   ```

2. **File permissions**
   ```bash
   # Ensure files have correct permissions
   chmod 600 sensitive_file.pem
   ```

3. **Secret not found**
   - Check secret name spelling
   - Ensure secret is set in correct repository/environment
   - Verify secret has a value (not empty)

### Debug Commands
```yaml
- name: Debug secrets availability
  run: |
    echo "Checking secret availability..."
    [ ! -z "${{ secrets.TELEGRAM_BOT_TOKEN }}" ] && echo "✅ TELEGRAM_BOT_TOKEN available" || echo "❌ TELEGRAM_BOT_TOKEN missing"
    [ ! -z "${{ secrets.GOOGLE_CREDENTIALS }}" ] && echo "✅ GOOGLE_CREDENTIALS available" || echo "❌ GOOGLE_CREDENTIALS missing"
    [ ! -z "${{ secrets.JIRA_PRIVATE_KEY }}" ] && echo "✅ JIRA_PRIVATE_KEY available" || echo "❌ JIRA_PRIVATE_KEY missing"
```

## Local Development

For local development, create a `.env` file (ensure it's in `.gitignore`):

```bash
# .env
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
JIRA_SERVER_URL=https://your-company.atlassian.net
GOOGLE_APPLICATION_CREDENTIALS=data/storage/google_credentials.json
```

And place your secure files in `data/storage/` directory:
```
data/storage/
├── google_credentials.json
├── jira_private_key.pem
└── .gitkeep
```

Make sure to add `data/storage/*` to your `.gitignore` (except `.gitkeep`).
