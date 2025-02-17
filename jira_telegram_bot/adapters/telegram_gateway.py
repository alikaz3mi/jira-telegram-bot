# jira_telegram_bot/adapters/telegram_gateway.py
from __future__ import annotations

from typing import Optional

import requests

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import TELEGRAM_WEBHOOK_SETTINGS
from jira_telegram_bot.use_cases.interface.telegram_gateway_interface import (
    TelegramGatewayInterface,
)


class TelegramGateway(TelegramGatewayInterface):
    """
    Concrete adapter to call the actual Telegram Bot API.
    """

    def __init__(self):
        self.token = TELEGRAM_WEBHOOK_SETTINGS.TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_message_id: Optional[int] = None,
        parse_mode: str = "Markdown",
    ):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_message_id:
            payload["reply_to_message_id"] = reply_message_id

        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            LOGGER.error(
                f"Failed to send Telegram message to chat_id={chat_id}: {resp.text}",
            )
