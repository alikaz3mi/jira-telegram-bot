from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import List
from typing import Optional

from jira_telegram_bot.entities.deadline_alert import DeadlineAlert


class NotificationLogRepositoryInterface(ABC):
    """Interface for managing notification logs to ensure idempotency."""
    
    @abstractmethod
    async def has_notification_been_sent(
        self,
        issue_key: str,
        chat_id: int,
        notification_date: datetime,
    ) -> bool:
        """
        Check if a notification has already been sent for an issue to a chat on a specific date.
        
        Args:
            issue_key: Jira issue key
            chat_id: Telegram chat ID
            notification_date: Date of the notification (YYYY-MM-DD)
            
        Returns:
            True if notification was already sent, False otherwise
        """
        pass
    
    @abstractmethod
    async def log_notification_sent(
        self,
        issue_key: str,
        chat_id: int,
        notification_date: datetime,
        alert: DeadlineAlert,
    ) -> None:
        """
        Log that a notification has been sent.
        
        Args:
            issue_key: Jira issue key
            chat_id: Telegram chat ID
            notification_date: Date of the notification
            alert: The deadline alert that was sent
        """
        pass
    
    @abstractmethod
    async def get_notification_history(
        self,
        issue_key: Optional[str] = None,
        chat_id: Optional[int] = None,
        days_back: int = 30,
    ) -> List[dict]:
        """
        Get notification history for debugging purposes.
        
        Args:
            issue_key: Filter by issue key (optional)
            chat_id: Filter by chat ID (optional)
            days_back: Number of days to look back
            
        Returns:
            List of notification log entries
        """
        pass
    
    @abstractmethod
    async def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """
        Clean up old notification logs to prevent file growth.
        
        Args:
            days_to_keep: Number of days of logs to retain
            
        Returns:
            Number of log entries removed
        """
        pass
