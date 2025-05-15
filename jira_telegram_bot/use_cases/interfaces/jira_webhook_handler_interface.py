"""Interface for Jira webhook handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any

from jira_telegram_bot.entities.api_schemas import WebhookResponse


class JiraWebhookHandlerInterface(ABC):
    """Interface for handling Jira webhook events.
    
    This interface defines the contract for services that process
    Jira webhook payloads.
    """
    
    @abstractmethod
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> WebhookResponse:
        """Process a Jira webhook event.
        
        Args:
            webhook_data: The webhook payload from Jira
            
        Returns:
            Response with status and message
        """
        pass
