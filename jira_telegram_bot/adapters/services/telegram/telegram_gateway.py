from __future__ import annotations

from typing import Optional, Any, List
import aiohttp
from io import BytesIO


import requests


from jira_telegram_bot.use_cases.interfaces.telegram_gateway_interface import (
    TelegramGatewayInterface,
)
from jira_telegram_bot.settings.telegram_settings import TelegramWebhookConnectionSettings, TelegramConnectionSettings
from jira_telegram_bot import LOGGER

class TelegramGateway(TelegramGatewayInterface):
    """
    Concrete adapter to call the actual Telegram Bot API.
    """

    def __init__(self, setting: TelegramWebhookConnectionSettings):
        self.token = setting.TOKEN
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


def send_telegram_message(
    chat_id: int,
    text: str,
    reply_message_id: Optional[int] = None,
    parse_mode: str = "Markdown",
):
    """Send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_SETTINGS.HOOK_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_message_id:
        payload["reply_parameters"] = {"message_id": reply_message_id}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        LOGGER.error(
            f"Failed to send Telegram message to chat_id={chat_id}: {resp.text}",
        )


async def fetch_and_store_media(
    media: Any,
    session: aiohttp.ClientSession,
    storage_list: List,
    filename: str,
    settings: TelegramConnectionSettings,
):
    """Fetch media from Telegram and store it in the provided storage list."""
    media_file = await media.get_file()
    file_url = (
        f"https://api.telegram.org/file/bot{TELEGRAM_SETTINGS.HOOK_TOKEN}/{media_file.file_path}"
    )
    async with session.get(file_url) as response:
        if response.status == 200:
            buffer = BytesIO(await response.read())
            storage_list.append((filename, buffer))
        else:
            LOGGER.error(
                f"Failed to fetch media: {media_file.file_path} (status {response.status})",
            )
