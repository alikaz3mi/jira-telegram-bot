# jira_telegram_bot/adapters/telegram_gateway.py
from __future__ import annotations

from io import BytesIO
from typing import Optional, Any, List

import aiohttp
import requests

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)


class NotificationGateway(NotificationGatewayInterface):
    """
    Concrete adapter to call the actual Telegram Bot API.
    """

    def __init__(self, token: str = None):
        self.token = token
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

    async def send_message_async(
        self,
        chat_id: int,
        text: str,
        reply_message_id: Optional[int] = None,
        parse_mode: str = "Markdown",
    ) -> Optional[str]:
        """Send a message to a Telegram chat asynchronously."""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }
            if reply_message_id:
                payload["reply_to_message_id"] = reply_message_id

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return str(result["result"]["message_id"])
                    else:
                        error_text = await resp.text()
                        LOGGER.error(
                            f"Failed to send Telegram message to chat_id={chat_id}: {error_text}",
                        )
                        return None
        except Exception as e:
            LOGGER.error(f"Error sending async Telegram message: {e}")
            return None

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        """Edit an existing message."""
        try:
            url = f"{self.base_url}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        error_text = await resp.text()
                        LOGGER.error(
                            f"Failed to edit Telegram message {message_id} in chat {chat_id}: {error_text}",
                        )
                        return False
        except Exception as e:
            LOGGER.error(f"Error editing Telegram message: {e}")
            return False
    
    async def get_me(self):
        """Get bot information."""
        url = f"{self.base_url}/getMe"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()["result"]
        else:
            LOGGER.error(f"Failed to get bot info: {resp.text}")
            return None


def send_telegram_message(
    chat_id: int,
    text: str,
    reply_message_id: Optional[int] = None,
    parse_mode: str = "Markdown",
    token: str = None,
):
    """Send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
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
    token: str = None,
):
    """Fetch media from Telegram and store it in the provided storage list."""
    media_file = await media.get_file()
    file_url = (
        f"https://api.telegram.org/file/bot{token}/{media_file.file_path}"
    )
    async with session.get(file_url) as response:
        if response.status == 200:
            buffer = BytesIO(await response.read())
            storage_list.append((filename, buffer))
        else:
            LOGGER.error(
                f"Failed to fetch media: {media_file.file_path} (status {response.status})",
            )
