#!/bin/bash

# Quick setup script for environment variables
# This script helps you set up your local .env file for testing

echo "🔧 Setting up environment variables for Jira Telegram Bot"
echo "=================================================="

# Create .env file
ENV_FILE=".env"

if [ -f "$ENV_FILE" ]; then
    echo "⚠️  .env file already exists. Creating backup..."
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d-%H%M%S)"
fi

echo "Creating new .env file..."

cat > "$ENV_FILE" << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/jira_bot_db

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Jira Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your_jira_username_here
JIRA_API_TOKEN=your_jira_api_token_here
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY

# AI Models Configuration
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Google Sheets Configuration (optional)
GOOGLE_SHEETS_CREDENTIALS=path_to_your_service_account_json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here

# GitLab Configuration (optional)
GITLAB_TOKEN=your_gitlab_token_here
GITLAB_PROJECT_ID=your_gitlab_project_id_here

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG
EOF

echo "✅ .env file created!"
echo ""
echo "🔍 Next steps:"
echo "1. Edit the .env file with your actual values:"
echo "   nano $ENV_FILE"
echo ""
echo "2. Required values to update:"
echo "   - TELEGRAM_BOT_TOKEN (get from @BotFather)"
echo "   - TELEGRAM_CHAT_ID (your chat ID)"
echo "   - JIRA_BASE_URL (your Jira instance)"
echo "   - JIRA_USERNAME (your Jira email)"
echo "   - JIRA_API_TOKEN (from Jira account settings)"
echo "   - JIRA_PROJECT_KEY (your project key)"
echo "   - DATABASE_URL (if using PostgreSQL)"
echo ""
echo "3. Optional values (if using these features):"
echo "   - OPENAI_API_KEY (for AI features)"
echo "   - GEMINI_API_KEY (for AI features)"
echo "   - GOOGLE_SHEETS_* (for Google Sheets integration)"
echo "   - GITLAB_* (for GitLab integration)"
echo ""
echo "⚠️  Remember to add .env to your .gitignore file!"
echo "⚠️  Never commit the .env file to version control!"

# Check if .gitignore exists and add .env if not present
if [ -f ".gitignore" ]; then
    if ! grep -q "^\.env$" .gitignore; then
        echo "Adding .env to .gitignore..."
        echo ".env" >> .gitignore
    fi
else
    echo "Creating .gitignore file..."
    echo ".env" > .gitignore
fi

echo ""
echo "🛡️  Security reminder:"
echo "- .env file contains sensitive information"
echo "- File permissions set to 600 (owner read/write only)"
chmod 600 "$ENV_FILE"

echo ""
echo "🧪 To test your configuration:"
echo "   python -m jira_telegram_bot"
echo ""
echo "📖 For deployment instructions, see docs/DEPLOYMENT_GUIDE.md"
