from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Optional


class TelegramGatewayInterface(ABC):
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
