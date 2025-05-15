"""API schema models package."""

__all__ = ["WebhookResponse", "JiraWebhookRequest", "TelegramUpdate"]

from jira_telegram_bot.entities.api_schemas.webhook_schemas import (
    WebhookResponse,
    JiraWebhookRequest,
    TelegramUpdate,
)
