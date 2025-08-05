#!/bin/bash

# Server deployment setup script for Jira Telegram Bot
# Run this script on your server as root to set up the deployment environment

set -e

# Configuration
APP_USER="jira-bot"
APP_GROUP="jira-bot"
APP_DIR="/opt/jira-telegram-bot"
SERVICE_FILES_DIR="$(dirname "$0")/systemd"

echo "🚀 Setting up Jira Telegram Bot deployment environment..."

# Create user and group
if ! id "$APP_USER" &>/dev/null; then
    echo "Creating user $APP_USER..."
    useradd --system --create-home --shell /bin/bash "$APP_USER"
    usermod -aG sudo "$APP_USER"
fi

# Create application directories
echo "Creating application directories..."
mkdir -p "$APP_DIR"/{current,backup,logs,data}
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"
chmod -R 755 "$APP_DIR"

# Install required system packages
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    rsync \
    postgresql-client \
    nginx \
    supervisor

# Install systemd service files
echo "Installing systemd service files..."
if [ -d "$SERVICE_FILES_DIR" ]; then
    cp "$SERVICE_FILES_DIR"/*.service /etc/systemd/system/
    systemctl daemon-reload
    
    # Enable services (but don't start them yet)
    systemctl enable jira-telegram-bot
    systemctl enable jira-telegram-bot-api
    systemctl enable jira-telegram-bot-scheduler
    
    echo "Services installed and enabled."
else
    echo "Warning: Service files directory not found at $SERVICE_FILES_DIR"
fi

# Create nginx configuration
echo "Creating nginx configuration..."
cat > /etc/nginx/sites-available/jira-telegram-bot << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain
    
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Enable nginx site (optional)
# ln -sf /etc/nginx/sites-available/jira-telegram-bot /etc/nginx/sites-enabled/
# nginx -t && systemctl reload nginx

# Create log rotation configuration
echo "Setting up log rotation..."
cat > /etc/logrotate.d/jira-telegram-bot << 'EOF'
/opt/jira-telegram-bot/current/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 jira-bot jira-bot
    postrotate
        systemctl reload jira-telegram-bot jira-telegram-bot-api jira-telegram-bot-scheduler
    endscript
}
EOF

# Set up SSH key for GitHub Actions (you'll need to add the public key manually)
echo "Setting up SSH directory for $APP_USER..."
sudo -u "$APP_USER" mkdir -p "/home/$APP_USER/.ssh"
sudo -u "$APP_USER" chmod 700 "/home/$APP_USER/.ssh"

# Create firewall rules (optional)
echo "Setting up firewall rules..."
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS

echo "✅ Server setup completed!"
echo ""
echo "Next steps:"
echo "1. Add your GitHub Actions public SSH key to /home/$APP_USER/.ssh/authorized_keys"
echo "2. Configure your GitHub repository secrets"
echo "3. Update the nginx configuration with your domain name"
echo "4. Run your first deployment from GitHub Actions"
echo ""
echo "Commands to check status:"
echo "  sudo systemctl status jira-telegram-bot"
echo "  sudo systemctl status jira-telegram-bot-api"
echo "  sudo systemctl status jira-telegram-bot-scheduler"
echo "  sudo journalctl -u jira-telegram-bot -f"
