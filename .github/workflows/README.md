# GitHub Actions Workflows

This repository contains several GitHub Actions workflows for continuous integration, security, and deployment.

## Workflows Overview

### 1. CI/CD Pipeline (`ci.yml`)
Main workflow that runs on every push and pull request to master/main/develop branches.

**Jobs:**
- **Code Quality Checks**: Black formatting, isort, flake8, MyPy
- **Unit Tests**: Runs unit tests with coverage reporting
- **Integration Tests**: Runs integration tests with PostgreSQL service
- **Security Scan**: Safety and Bandit security scanning
- **Docker Build**: Builds and tests Docker image
- **Deploy**: Deploys to production (only on master branch)

### 2. Dependency Updates (`dependencies.yml`)
Scheduled workflow that runs weekly to check and update dependencies.

**Features:**
- Automated dependency updates using pip-tools
- Security vulnerability scanning
- Creates pull requests with updates

### 3. Release (`release.yml`)
Handles version releases and Docker image publishing.

**Triggers:**
- Git tags matching `v*.*.*` pattern
- Manual workflow dispatch

**Features:**
- Creates GitHub releases with changelog
- Builds and publishes Python packages
- Builds and pushes Docker images with version tags
- Sends Telegram notifications

## Required Secrets

Configure these secrets in your repository settings (`Settings > Secrets and variables > Actions`):

### Essential Secrets
- `GITHUB_TOKEN`: Automatically provided by GitHub
- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password or access token

### Application Secrets
- `GOOGLE_CREDENTIALS`: Base64 encoded Google service account JSON
- `JIRA_PRIVATE_KEY`: Base64 encoded JIRA private key file
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for notifications
- `TELEGRAM_CHAT_ID`: Telegram chat ID for notifications

### Environment Variables
The workflows set these environment variables for testing:
- `DATABASE_URL`: PostgreSQL connection string (test database)
- `JIRA_SERVER_URL`: JIRA server URL
- `TELEGRAM_BOT_TOKEN`: Bot token for testing

## Environments

### Production Environment
Create a `production` environment in your repository settings for deployment approvals:
1. Go to `Settings > Environments`
2. Create `production` environment
3. Add protection rules (required reviewers, wait timer, etc.)

## Status Badges

Add these badges to your README.md:

```markdown
[![CI/CD Pipeline](https://github.com/alikaz3mi/jira-telegram-bot/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/alikaz3mi/jira-telegram-bot/actions/workflows/ci.yml)
[![Security Scan](https://github.com/alikaz3mi/jira-telegram-bot/workflows/CI/CD%20Pipeline/badge.svg?event=schedule)](https://github.com/alikaz3mi/jira-telegram-bot/actions)
[![codecov](https://codecov.io/gh/alikaz3mi/jira-telegram-bot/branch/master/graph/badge.svg)](https://codecov.io/gh/alikaz3mi/jira-telegram-bot)
```

## Customization

### Adding New Jobs
1. Edit the appropriate workflow file
2. Follow the existing pattern for job dependencies
3. Use caching for dependencies when possible

### Modifying Test Commands
Update the test commands in the workflow files to match your Make targets:
- Unit tests: `make unit-tests`
- Integration tests: `make integration-tests`

### Deployment Customization
Edit the `deploy` job in `ci.yml` to match your deployment strategy:
- SSH deployment
- Kubernetes deployment
- Cloud provider deployment
- Webhook triggers
