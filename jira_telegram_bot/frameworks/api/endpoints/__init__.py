"""API endpoints package."""

__all__ = ["JiraWebhookEndpoint", "TelegramWebhookEndpoint"]

from jira_telegram_bot.frameworks.api.endpoints.jira_webhook import JiraWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints.telegram_webhook import TelegramWebhookEndpoint
