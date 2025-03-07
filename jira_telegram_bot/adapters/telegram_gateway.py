from __future__ import annotations

from typing import Optional

import requests

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.telegram_settings import TelegramWebhookConnectionSettings
from jira_telegram_bot.settings import TELEGRAM_WEBHOOK_SETTINGS
from jira_telegram_bot.use_cases.interface.telegram_gateway_interface import (
    TelegramGatewayInterface,
)


class TelegramGateway(TelegramGatewayInterface):
    """
    Concrete adapter to call the actual Telegram Bot API.
    """

    def __init__(self,
                 settings: TelegramWebhookConnectionSettings = TELEGRAM_WEBHOOK_SETTINGS
                 ):
        self.token = settings.TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.send_message_url = f"{self.base_url}/sendMessage"


    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_message_id: Optional[int] = None,
        parse_mode: str = "Markdown",
    ):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_message_id:
            payload["reply_to_message_id"] = reply_message_id

        resp = requests.post(self.send_message_url, json=payload)
        if resp.status_code != 200:
            LOGGER.error(
                f"Failed to send Telegram message to chat_id={chat_id}: {resp.text}",
            )

    def send_telegram_message(
            self,
            chat_id: int,
            text: str,
            reply_message_id: Optional[int] = None,
    ):
        """Send a message to a Telegram chat."""
        payload = {"chat_id": chat_id, "text": text}
        if reply_message_id:
            payload["reply_parameters"] = {"message_id": reply_message_id}
        resp = requests.post(self.send_message_url, json=payload)
        if resp.status_code != 200:
            LOGGER.error(
                f"Failed to send Telegram message to chat_id={chat_id}: {resp.text}",
            )