from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import List
from typing import Optional

from jira_telegram_bot.entities.deadline_alert import DeadlineAlert


class TelegramNotifierInterface(ABC):
    """Interface for sending Telegram notifications."""
    
    @abstractmethod
    async def send_personal_notification(
        self,
        chat_id: int,
        alert: DeadlineAlert,
    ) -> bool:
        """
        Send a deadline alert to a personal chat.
        
        Args:
            chat_id: Telegram chat ID for the user
            alert: Deadline alert to send
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_group_notification(
        self,
        chat_id: int,
        alerts: List[DeadlineAlert],
        mention_users: bool = True,
    ) -> bool:
        """
        Send deadline alerts to a group chat.
        
        Args:
            chat_id: Telegram group chat ID
            alerts: List of deadline alerts to send
            mention_users: Whether to mention users in the group
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def format_alert_message(
        self,
        alert: DeadlineAlert,
        include_mention: bool = False,
        telegram_username: Optional[str] = None,
    ) -> str:
        """
        Format a deadline alert as a Telegram message.
        
        Args:
            alert: Deadline alert to format
            include_mention: Whether to include user mention
            telegram_username: Telegram username for mention
            
        Returns:
            Formatted message string
        """
        pass
