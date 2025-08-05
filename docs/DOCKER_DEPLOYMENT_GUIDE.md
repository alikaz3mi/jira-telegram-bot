# Docker Deployment Guide

This guide explains how to deploy your Jira Telegram Bot service using Docker and GitHub Actions.

## 📋 Prerequisites

1. **Server Requirements**:
   - Ubuntu 20.04+ or similar Linux distribution
   - Docker and Docker Compose installed
   - SSH access to the server
   - At least 2GB RAM and 10GB storage

2. **GitHub Repository**:
   - GitHub repository with your code
   - GitHub Actions enabled

## 🔧 Step-by-Step Deployment Process

### Step 1: Prepare Your Server

1. **Install Docker and Docker Compose**:
   ```bash
   # Update package index
   sudo apt update
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Add user to docker group
   sudo usermod -aG docker $USER
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   
   # Logout and login again for group changes to take effect
   ```

2. **Create deployment directory**:
   ```bash
   sudo mkdir -p /opt/jira-telegram-bot
   sudo chown $USER:$USER /opt/jira-telegram-bot
   cd /opt/jira-telegram-bot
   ```

### Step 2: Set Up GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

#### 🔐 Server Access Secrets
- `SERVER_HOST`: Your server's IP address or domain
- `SERVER_USER`: SSH username (e.g., `ubuntu`, `root`)
- `SERVER_SSH_KEY`: Your private SSH key for server access
- `SERVER_PORT`: SSH port (optional, defaults to 22)

#### 🤖 Telegram Configuration
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID for notifications

#### 🔗 Jira Configuration
- `JIRA_BASE_URL`: Your Jira instance URL (e.g., `https://company.atlassian.net`)
- `JIRA_USERNAME`: Your Jira username/email
- `JIRA_API_TOKEN`: Your Jira API token
- `JIRA_PROJECT_KEY`: Your Jira project key

#### 🧠 AI Models Configuration
- `OPENAI_API_KEY`: Your OpenAI API key
- `GEMINI_API_KEY`: Your Google Gemini API key

#### 📊 Google Sheets Configuration
- `GOOGLE_SHEETS_CREDENTIALS`: Your Google Service Account JSON credentials (as string)
- `GOOGLE_SHEETS_SPREADSHEET_ID`: Your Google Sheets spreadsheet ID

#### 🦊 GitLab Configuration
- `GITLAB_TOKEN`: Your GitLab access token
- `GITLAB_PROJECT_ID`: Your GitLab project ID

#### 🗄️ Database Configuration
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@postgres:5432/jira_telegram_bot`)
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database username
- `POSTGRES_PASSWORD`: Database password

### Step 3: Prepare Environment Files on Server

1. **Create the environment file manually on your server**:
   ```bash
   cd /opt/jira-telegram-bot
   nano .env
   ```

2. **Add your environment variables**:
   ```env
   # Database Configuration
   DATABASE_URL=postgresql://jira_bot:your_password@postgres:5432/jira_telegram_bot
   POSTGRES_DB=jira_telegram_bot
   POSTGRES_USER=jira_bot
   POSTGRES_PASSWORD=your_secure_password
   
   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   
   # Jira Configuration
   JIRA_BASE_URL=https://your-company.atlassian.net
   JIRA_USERNAME=your-email@company.com
   JIRA_API_TOKEN=your_jira_api_token
   JIRA_PROJECT_KEY=PROJ
   
   # AI Models Configuration
   OPENAI_API_KEY=your_openai_api_key
   GEMINI_API_KEY=your_gemini_api_key
   
   # Google Sheets Configuration
   GOOGLE_SHEETS_CREDENTIALS={"type":"service_account",...}
   GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
   
   # GitLab Configuration
   GITLAB_TOKEN=your_gitlab_token
   GITLAB_PROJECT_ID=your_project_id
   
   # Application Configuration
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   ```

3. **Secure the environment file**:
   ```bash
   chmod 600 .env
   ```

### Step 4: Deploy Using GitHub Actions

#### Method 1: Automatic Deployment (Recommended)
1. Push your code to the `master` or `main` branch
2. GitHub Actions will automatically:
   - Build Docker image
   - Push to GitHub Container Registry
   - Deploy to your server
   - Send notification to Telegram

#### Method 2: Manual Deployment
1. Go to your GitHub repository → Actions tab
2. Select "Deploy to Server" workflow
3. Click "Run workflow"
4. Choose environment (production/staging)
5. Click "Run workflow"

### Step 5: Verify Deployment

1. **Check container status**:
   ```bash
   cd /opt/jira-telegram-bot
   sudo docker-compose -f docker-compose.prod.yml ps
   ```

2. **View logs**:
   ```bash
   # All services
   sudo docker-compose -f docker-compose.prod.yml logs
   
   # Specific service
   sudo docker-compose -f docker-compose.prod.yml logs jira-telegram-bot-api
   ```

3. **Test API endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

## 🔄 Managing Your Deployment

### Update Application
Simply push to your main branch - GitHub Actions will handle the deployment automatically.

### Manual Commands
```bash
cd /opt/jira-telegram-bot

# Stop services
sudo docker-compose -f docker-compose.prod.yml down

# Start services
sudo docker-compose -f docker-compose.prod.yml up -d

# Restart specific service
sudo docker-compose -f docker-compose.prod.yml restart jira-telegram-bot-api

# View logs
sudo docker-compose -f docker-compose.prod.yml logs -f

# Update to latest image
sudo docker-compose -f docker-compose.prod.yml pull
sudo docker-compose -f docker-compose.prod.yml up -d
```

### Backup Data
```bash
# Backup data directory
sudo tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Backup database
sudo docker exec jira-telegram-bot-postgres pg_dump -U jira_bot jira_telegram_bot > backup-db-$(date +%Y%m%d).sql
```

## 🚨 Troubleshooting

### Common Issues

1. **Container fails to start**:
   ```bash
   # Check logs
   sudo docker-compose -f docker-compose.prod.yml logs jira-telegram-bot
   
   # Check environment variables
   sudo docker-compose -f docker-compose.prod.yml config
   ```

2. **Permission denied errors**:
   ```bash
   # Fix data directory permissions
   sudo chown -R $USER:$USER data logs
   ```

3. **Database connection issues**:
   ```bash
   # Check PostgreSQL container
   sudo docker-compose -f docker-compose.prod.yml logs postgres
   
   # Test database connection
   sudo docker exec -it jira-telegram-bot-postgres psql -U jira_bot -d jira_telegram_bot
   ```

4. **GitHub Actions deployment fails**:
   - Check server SSH access
   - Verify all secrets are set correctly
   - Check server disk space: `df -h`
   - Check Docker daemon: `sudo systemctl status docker`

## 🔒 Security Best Practices

1. **Use strong passwords** for database and other services
2. **Regularly update** Docker images and server packages
3. **Monitor logs** for suspicious activities
4. **Backup data** regularly
5. **Use firewall** to restrict access to necessary ports only
6. **Keep secrets secure** - never commit them to repository

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review container logs
3. Verify all environment variables are set correctly
4. Check GitHub Actions logs for deployment issues

Remember to replace all placeholder values with your actual configuration!
