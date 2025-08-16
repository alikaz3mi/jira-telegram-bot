from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Optional


class NotificationGatewayInterface(ABC):
    @abstractmethod
    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_message_id: Optional[int] = None,
        parse_mode: str = "Markdown",
    ):
        """Send a message to a Telegram chat."""
        pass

    @abstractmethod
    async def send_message_async(
        self,
        chat_id: int,
        text: str,
        reply_message_id: Optional[int] = None,
        parse_mode: str = "Markdown",
    ) -> Optional[str]:
        """Send a message to a Telegram chat asynchronously.
        
        Args:
            chat_id: Telegram chat/channel ID
            text: Message text to send
            reply_message_id: ID of message to reply to
            parse_mode: Parse mode (e.g., "Markdown", "HTML")
            
        Returns:
            Message ID if successful, None otherwise
        """
        pass

    @abstractmethod
    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        """Edit an existing message.
        
        Args:
            chat_id: Telegram chat/channel ID
            message_id: ID of the message to edit
            text: New message text
            parse_mode: Parse mode (e.g., "Markdown", "HTML")
            
        Returns:
            True if successful, False otherwise
        """
        pass
    