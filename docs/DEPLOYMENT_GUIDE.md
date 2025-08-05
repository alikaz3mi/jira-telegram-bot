# Complete Deployment Guide

This guide will walk you through deploying your Jira Telegram Bot service to your server using GitHub Actions with secure environment files.

## 📋 Prerequisites

Before starting, ensure you have:

- A Linux server (Ubuntu 20.04+ recommended)
- Root access to the server
- A GitHub repository with your code
- All necessary API keys and credentials

## 🔧 Step 1: Server Preparation

### 1.1 Connect to Your Server
```bash
ssh root@your-server-ip
```

### 1.2 Update System
```bash
apt update && apt upgrade -y
```

### 1.3 Run the Setup Script
```bash
# Copy the setup script to your server
wget https://raw.githubusercontent.com/your-username/jira-telegram-bot/master/deploy/setup-server.sh
chmod +x setup-server.sh
./setup-server.sh
```

Alternatively, you can run the commands manually:

```bash
# Create application user
useradd --system --create-home --shell /bin/bash jira-bot
usermod -aG sudo jira-bot

# Create directories
mkdir -p /opt/jira-telegram-bot/{current,backup,logs,data}
chown -R jira-bot:jira-bot /opt/jira-telegram-bot

# Install dependencies
apt install -y python3 python3-pip python3-venv git curl rsync postgresql-client nginx
```

## 🔐 Step 2: SSH Key Setup for GitHub Actions

### 2.1 Generate SSH Key Pair
On your local machine or in the GitHub Actions environment:

```bash
ssh-keygen -t ed25519 -C "github-actions@your-domain.com" -f github-actions-key
```

### 2.2 Add Public Key to Server
Copy the public key to your server:

```bash
# On your server
sudo -u jira-bot mkdir -p /home/jira-bot/.ssh
sudo -u jira-bot chmod 700 /home/jira-bot/.ssh

# Add the public key content
sudo -u jira-bot tee /home/jira-bot/.ssh/authorized_keys << 'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... github-actions@your-domain.com
EOF

sudo -u jira-bot chmod 600 /home/jira-bot/.ssh/authorized_keys
```

## 🔒 Step 3: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

### 3.1 Server Connection Secrets
- `SSH_PRIVATE_KEY`: Content of the private key file (github-actions-key)
- `SERVER_HOST`: Your server IP address or domain
- `SERVER_USER`: `jira-bot`

### 3.2 Application Secrets
Set up these secrets with your actual values:

#### Database
- `DATABASE_URL`: `postgresql://user:password@localhost:5432/jira_bot_db`

#### Telegram
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID

#### Jira
- `JIRA_BASE_URL`: `https://your-company.atlassian.net`
- `JIRA_USERNAME`: Your Jira username/email
- `JIRA_API_TOKEN`: Your Jira API token
- `JIRA_PROJECT_KEY`: Your Jira project key (e.g., 'PROJ')

#### AI Services
- `OPENAI_API_KEY`: Your OpenAI API key
- `GEMINI_API_KEY`: Your Google Gemini API key

#### Google Sheets
- `GOOGLE_SHEETS_CREDENTIALS`: Your Google Service Account JSON (base64 encoded)
- `GOOGLE_SHEETS_SPREADSHEET_ID`: Your Google Sheets ID

#### GitLab (if used)
- `GITLAB_TOKEN`: Your GitLab access token
- `GITLAB_PROJECT_ID`: Your GitLab project ID

## 🚀 Step 4: Set Up Database (PostgreSQL)

### 4.1 Install PostgreSQL
```bash
apt install -y postgresql postgresql-contrib
sudo -u postgres createuser --interactive
sudo -u postgres createdb jira_bot_db
```

### 4.2 Configure Database Access
```bash
sudo -u postgres psql
```

```sql
ALTER USER jira_bot PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE jira_bot_db TO jira_bot;
\q
```

## 📝 Step 5: Environment Configuration

The deployment workflow will automatically create the `.env` file from GitHub Secrets, but you can verify the format:

```bash
# This file will be created automatically by GitHub Actions
# Location: /opt/jira-telegram-bot/current/.env

DATABASE_URL=postgresql://jira_bot:password@localhost:5432/jira_bot_db
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your_username
JIRA_API_TOKEN=your_api_token
JIRA_PROJECT_KEY=PROJ
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 🔧 Step 6: Deploy Your Application

### 6.1 Automatic Deployment (Recommended)
Push to your master branch or manually trigger the deployment:

```bash
git push origin master
```

Or trigger manually from GitHub:
1. Go to Actions tab in your repository
2. Select "Deploy to Server" workflow
3. Click "Run workflow"
4. Choose environment (production/staging)

### 6.2 Manual Deployment (if needed)
```bash
# On your server as jira-bot user
cd /opt/jira-telegram-bot/current
git clone https://github.com/your-username/jira-telegram-bot.git .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🛠️ Step 7: Service Management

### 7.1 Start Services
```bash
sudo systemctl start jira-telegram-bot
sudo systemctl start jira-telegram-bot-api
sudo systemctl start jira-telegram-bot-scheduler
```

### 7.2 Check Service Status
```bash
sudo systemctl status jira-telegram-bot
sudo systemctl status jira-telegram-bot-api
sudo systemctl status jira-telegram-bot-scheduler
```

### 7.3 View Logs
```bash
# Real-time logs
sudo journalctl -u jira-telegram-bot -f
sudo journalctl -u jira-telegram-bot-api -f
sudo journalctl -u jira-telegram-bot-scheduler -f

# Application logs
tail -f /opt/jira-telegram-bot/current/logs/app.log
```

## 🌐 Step 8: Web Server Configuration (Optional)

### 8.1 Configure Nginx
Edit the nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/jira-telegram-bot
```

Replace `your-domain.com` with your actual domain and enable the site:

```bash
sudo ln -sf /etc/nginx/sites-available/jira-telegram-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8.2 SSL Certificate (Recommended)
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

## 🔍 Step 9: Verification

### 9.1 Test Deployment
1. Check if services are running: `sudo systemctl status jira-telegram-bot*`
2. Test API endpoint: `curl http://localhost:8000/health`
3. Send a test message to your Telegram bot
4. Check application logs for any errors

### 9.2 Test GitHub Actions Deployment
1. Make a small change to your code
2. Push to master branch
3. Monitor the GitHub Actions workflow
4. Verify the deployment completed successfully

## 🚨 Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Verify SSH key is correctly added to server
   - Check server firewall settings
   - Ensure SSH service is running

2. **Permission Denied**
   - Check file ownership: `ls -la /opt/jira-telegram-bot/`
   - Fix permissions: `sudo chown -R jira-bot:jira-bot /opt/jira-telegram-bot/`

3. **Service Failed to Start**
   - Check logs: `sudo journalctl -u jira-telegram-bot`
   - Verify environment file: `sudo -u jira-bot cat /opt/jira-telegram-bot/current/.env`
   - Check Python dependencies: `sudo -u jira-bot /opt/jira-telegram-bot/current/venv/bin/pip list`

4. **Database Connection Issues**
   - Test connection: `sudo -u jira-bot psql $DATABASE_URL`
   - Check PostgreSQL status: `sudo systemctl status postgresql`

### Useful Commands

```bash
# Restart all services
sudo systemctl restart jira-telegram-bot*

# View all logs
sudo journalctl -u jira-telegram-bot* --since today

# Check disk space
df -h /opt/jira-telegram-bot/

# Check memory usage
free -h
ps aux | grep jira-telegram-bot

# Manual backup
sudo -u jira-bot cp -r /opt/jira-telegram-bot/current /opt/jira-telegram-bot/backup/manual-$(date +%Y%m%d-%H%M%S)
```

## 🔄 Step 10: Continuous Updates

Your deployment is now set up for automatic updates:

1. **Push to master** → Automatic deployment
2. **Manual deployment** → Use GitHub Actions workflow dispatch
3. **Rollback** → Restore from backup in `/opt/jira-telegram-bot/backup/`

## 🛡️ Security Best Practices

1. **Regular Updates**: Keep your server and dependencies updated
2. **Firewall**: Only open necessary ports (22, 80, 443)
3. **SSH Keys**: Use key-based authentication, disable password login
4. **Secrets**: Never commit secrets to repository
5. **Monitoring**: Set up log monitoring and alerts
6. **Backups**: Regular database and application backups

## 📞 Support

If you encounter issues:
1. Check the logs first
2. Review this guide
3. Check GitHub Actions workflow logs
4. Open an issue in the repository

Your Jira Telegram Bot is now deployed and ready to use! 🎉
