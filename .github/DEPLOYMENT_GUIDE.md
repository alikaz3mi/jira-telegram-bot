# Docker Deployment Guide for Jira Telegram Bot

This guide explains how to deploy your Jira Telegram Bot service using Docker with GitHub Actions and secure environment files.

## 📋 Prerequisites

- Server with Docker and Docker Compose installed
- SSH access to your server
- GitHub repository with proper permissions
- Your existing `docker-compose.prod.yml` file

## 🛠️ Step-by-Step Deployment Process

### Step 1: Set up GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

#### Server Connection Secrets
```
DEPLOY_HOST         = your-server-ip-or-domain
DEPLOY_USER         = your-ssh-username
DEPLOY_SSH_KEY      = your-private-ssh-key-content
DEPLOY_PORT         = 22 (optional, defaults to 22)
DEPLOY_PATH         = /opt/jira-telegram-bot
```

#### Optional Notification Secrets
```
TELEGRAM_BOT_TOKEN  = your-telegram-bot-token (for deployment notifications)
TELEGRAM_CHAT_ID    = your-telegram-chat-id (for deployment notifications)
```

### Step 2: Prepare Your Server

1. **Connect to your server:**
   ```bash
   ssh your-user@your-server
   ```

2. **Create deployment directory:**
   ```bash
   sudo mkdir -p /opt/jira-telegram-bot
   sudo chown $USER:$USER /opt/jira-telegram-bot
   cd /opt/jira-telegram-bot
   ```

3. **Copy your docker-compose.prod.yml to the server:**
   ```bash
   # From your local machine, copy the file to server
   scp docker-compose.prod.yml your-user@your-server:/opt/jira-telegram-bot/
   ```

4. **Create your .env file on the server:**
   ```bash
   cd /opt/jira-telegram-bot
   nano .env
   ```

   Add your environment variables (see example below).

### Step 3: Environment Variables Setup

Create a `.env` file on your server with your actual values:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Jira Configuration
JIRA_SERVER_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-jira-email@company.com
JIRA_API_TOKEN=your_jira_api_token_here
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY

# Database Configuration
POSTGRES_DB=jira_telegram_bot
POSTGRES_USER=jira_bot
POSTGRES_PASSWORD=your_secure_database_password_here
DATABASE_URL=postgresql://jira_bot:your_secure_database_password_here@postgres:5432/jira_telegram_bot

# Redis Configuration (if used)
REDIS_URL=redis://redis:6379/0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO

# AI Models (if used)
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Google Sheets (if used)
GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials/google-sheets-credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here

# GitLab Integration (if used)
GITLAB_TOKEN=your_gitlab_token_here
GITLAB_PROJECT_ID=your_gitlab_project_id_here
```

### Step 4: Secure Your .env File

```bash
# Set proper permissions (readable only by owner)
chmod 600 /opt/jira-telegram-bot/.env

# Verify permissions
ls -la /opt/jira-telegram-bot/.env
# Should show: -rw------- 1 youruser youruser
```

### Step 5: Test Docker Compose Locally

Before deploying, test your setup:

```bash
# Navigate to deployment directory
cd /opt/jira-telegram-bot

# Pull images
docker compose -f docker-compose.prod.yml pull

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs

# Stop services (for testing)
docker compose -f docker-compose.prod.yml down
```

### Step 6: Deploy Using GitHub Actions

1. **Push to master branch** or **manually trigger the workflow:**
   - Go to GitHub → Actions → Deploy to Production → Run workflow

2. **Monitor the deployment:**
   - Watch the GitHub Actions logs
   - Check your server logs if needed

### Step 7: Verify Deployment

After deployment, verify everything is working:

```bash
# Check running containers
cd /opt/jira-telegram-bot
docker compose -f docker-compose.prod.yml ps

# Check logs
docker compose -f docker-compose.prod.yml logs -f

# Test API endpoint (if available)
curl http://localhost:8000/health

# Test Telegram bot functionality
# Send a message to your bot to verify it's working
```

## 🔧 Maintenance Commands

### View Logs
```bash
cd /opt/jira-telegram-bot
docker compose -f docker-compose.prod.yml logs -f [service-name]
```

### Restart Services
```bash
cd /opt/jira-telegram-bot
docker compose -f docker-compose.prod.yml restart [service-name]
```

### Update Services
```bash
cd /opt/jira-telegram-bot
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Backup Database
```bash
docker exec jira-telegram-bot-postgres pg_dump -U jira_bot jira_telegram_bot > backup_$(date +%Y%m%d_%H%M%S).sql
```

## 🚨 Troubleshooting

### Common Issues

1. **Permission Denied for .env file:**
   ```bash
   chmod 600 /opt/jira-telegram-bot/.env
   ```

2. **Docker Compose not found:**
   ```bash
   # Install Docker Compose
   sudo apt update
   sudo apt install docker-compose-plugin
   ```

3. **Services not starting:**
   ```bash
   # Check logs for specific service
   docker compose -f docker-compose.prod.yml logs [service-name]
   ```

4. **Database connection issues:**
   - Verify DATABASE_URL in .env file
   - Check if PostgreSQL container is running
   - Verify network connectivity between containers

### Logs and Monitoring

- **Application logs:** `docker compose logs jira-telegram-bot`
- **API logs:** `docker compose logs jira-telegram-bot-api`
- **Database logs:** `docker compose logs postgres`
- **System logs:** `journalctl -u docker`

## 🔒 Security Best Practices

1. **Always use strong passwords** for database and API keys
2. **Keep .env file permissions restrictive** (600)
3. **Regularly update Docker images** for security patches
4. **Use SSH keys instead of passwords** for server access
5. **Enable firewall** and restrict access to necessary ports only
6. **Regularly backup your data** and test restore procedures

## 📞 Support

If you encounter issues:
1. Check the GitHub Actions logs
2. Check Docker container logs
3. Verify environment variables
4. Check network connectivity
5. Review the troubleshooting section above
