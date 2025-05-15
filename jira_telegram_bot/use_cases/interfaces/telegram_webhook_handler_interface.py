"""Interface for Telegram webhook handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any

from jira_telegram_bot.entities.api_schemas import WebhookResponse


class TelegramWebhookHandlerInterface(ABC):
    """Interface for handling Telegram webhook events.
    
    This interface defines the contract for services that process
    Telegram webhook payloads.
    """
    
    @abstractmethod
    async def process_update(self, update_data: Dict[str, Any]) -> WebhookResponse:
        """Process a Telegram update event.
        
        Args:
            update_data: The update payload from Telegram
            
        Returns:
            Response with status and message
        """
        pass
