"""Jira webhook endpoint."""

from __future__ import annotations

from jira_telegram_bot.adapters.controllers.jira_webhook_controller import JiraWebhookController
from jira_telegram_bot.frameworks.api.endpoints.webhook_endpoint import WebhookEndpoint


class JiraWebhookEndpoint(WebhookEndpoint):
    """API endpoint for handling Jira webhook events."""
    
    def __init__(self, jira_webhook_controller: JiraWebhookController):
        """Initialize the endpoint.
        
        Args:
            jira_webhook_controller: Controller for handling Jira webhooks
        """
        super().__init__(
            controller=jira_webhook_controller,
            route_prefix="/webhook/jira",
            route_tags=["Webhooks"]
        )
