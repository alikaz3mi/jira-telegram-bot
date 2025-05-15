"""Webhook handling use cases."""

__all__ = ["JiraWebhookUseCase", "TelegramWebhookUseCase"]

from jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case import JiraWebhookUseCase
from jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case import TelegramWebhookUseCase
