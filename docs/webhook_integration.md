# Webhook Integration

This document explains how to set up and use the webhook integration features of the Jira Telegram Bot.

## Overview

The Jira Telegram Bot supports bidirectional webhook integration:

1. **Jira → Telegram**: Receive notifications in Telegram when Jira issues are updated
2. **Telegram → Jira**: Create and update Jira issues from Telegram messages

This integration allows for seamless real-time synchronization between your Jira projects and Telegram channels or groups.

## Architecture

The webhook integration follows Clean Architecture principles:

- **Entities Layer**: Defines data structures (WebhookResponse, JiraWebhookRequest, TelegramUpdate)
- **Use Case Layer**: Contains business logic for processing webhooks (JiraWebhookUseCase, TelegramWebhookUseCase)
- **Interface Layer**: Defines contracts for webhook handlers (JiraWebhookHandlerInterface, TelegramWebhookHandlerInterface)
- **Framework Layer**: Implements FastAPI endpoints (JiraWebhookEndpoint, TelegramWebhookEndpoint)

## Webhook Endpoints

### Jira Webhook

**Endpoint**: `/webhook/jira/`

This endpoint receives events from Jira when issues are created, updated, or commented on. The webhook will:

1. Receive the Jira event payload
2. Extract the issue key and event type
3. Find any associated Telegram messages/chats
4. Send appropriate notifications to Telegram

**Supported Events**:
- Issue creation
- Issue updates (status changes, assignee changes)
- Comments
- Attachments

### Telegram Webhook

**Endpoint**: `/webhook/telegram/`

This endpoint receives events from Telegram when messages are sent to the bot. The webhook will:

1. Receive the Telegram update payload
2. Process messages based on context (new message, reply, channel post)
3. Create or update Jira issues as needed
4. Send confirmation messages to Telegram

**Supported Events**:
- Channel posts (creates new Jira issues)
- Replies to existing issues (adds comments to Jira)
- Direct messages (for commands and queries)

## Configuration

### Environment Variables

Set these environment variables for webhook functionality:

```
# Telegram Webhook Settings
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram/
TELEGRAM_HOOK_TOKEN=your-telegram-bot-token

# Jira Webhook Settings
JIRA_SERVER=https://your-jira-instance.atlassian.net
JIRA_USER=your-jira-email@example.com
JIRA_TOKEN=your-jira-api-token
```

### Setting Up Webhooks

Use the provided script to easily configure webhooks:

```bash
python scripts/configure_webhooks.py --base-url https://your-domain.com
```

This script will:
1. Register the Telegram webhook with the Telegram API
2. Create a webhook in your Jira instance pointing to your server

#### Options:

- `--service jira|telegram|all`: Configure only specific webhooks
- `--remove`: Remove existing webhooks instead of creating them

### Testing Webhooks

For local development, you can use ngrok to create a secure tunnel:

```bash
ngrok http 8000
```

Then use the provided ngrok URL as your base URL when configuring webhooks.

## Security Considerations

- Telegram webhooks are secured by the bot token
- Jira webhooks should be secured using an authentication mechanism (JWT, OAuth, etc.)
- All webhook endpoints use HTTPS encryption
- Consider implementing rate limiting for production use

## Troubleshooting

Common issues:

1. **Webhook not receiving events**:
   - Check that the public URL is accessible
   - Verify webhook registration was successful
   - Check firewall and network settings

2. **Authentication failures**:
   - Verify your API tokens are correct
   - Check for expired credentials

3. **Telegram message not creating Jira issues**:
   - Ensure the bot has necessary permissions
   - Check if user is in the allowed users list
