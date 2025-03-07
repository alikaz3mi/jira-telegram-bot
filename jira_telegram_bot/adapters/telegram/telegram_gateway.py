from __future__ import annotations

from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests
from aiohttp import ClientSession

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import TELEGRAM_WEBHOOK_SETTINGS
from jira_telegram_bot.settings.telegram_settings import (
    TelegramWebhookConnectionSettings,
)
from jira_telegram_bot.use_cases.interface.telegram_gateway_interface import (
    TelegramGatewayInterface,
)


class TelegramGateway(TelegramGatewayInterface):
    """
    Concrete adapter to call the actual Telegram Bot API.
    """

    def __init__(
        self,
        settings: TelegramWebhookConnectionSettings = TELEGRAM_WEBHOOK_SETTINGS,
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

    async def fetch_and_store_media(
        self,
        media: Any,
        session: ClientSession,
        storage_list: List,
        filename: str,
    ):
        """Fetch media from Telegram and store it in the provided storage list."""
        media_file = await media.get_file()
        file_url = f"{self.base_url}/{media_file.file_path}"
        async with session.get(file_url) as response:
            if response.status == 200:
                buffer = BytesIO(await response.read())
                storage_list.append((filename, buffer))
            else:
                LOGGER.error(
                    f"Failed to fetch media: {media_file.file_path} (status {response.status})",
                )

    async def process_media_group(self, attachments, messages: List[Dict[str, Any]]):
        async with ClientSession() as session:
            for idx, msg in enumerate(messages):
                if "photo" in msg:
                    photo_array = msg["photo"]
                    file_info = photo_array[-1]
                    file_id = file_info["file_id"]
                    mock_media = MockTelegramPhoto(file_id, self.token)
                    await self.fetch_and_store_media(
                        mock_media,
                        session,
                        attachments["images"],
                        f"image_{idx}.jpg",
                    )
                elif "document" in msg:
                    doc = msg["document"]
                    file_id = doc["file_id"]
                    file_name = doc.get("file_name", f"document_{idx}")
                    mock_media = MockTelegramDocument(file_id, self.token)
                    await self.fetch_and_store_media(
                        mock_media,
                        session,
                        attachments["documents"],
                        file_name,
                    )
                elif "video" in msg:
                    vid = msg["video"]
                    file_id = vid["file_id"]
                    mock_media = MockTelegramVideo(file_id, self.token)
                    await self.fetch_and_store_media(
                        mock_media,
                        session,
                        attachments["videos"],
                        f"video_{idx}.mp4",
                    )
                elif "audio" in msg:
                    aud = msg["audio"]
                    file_id = aud["file_id"]
                    mock_media = MockTelegramAudio(file_id, self.token)
                    await self.fetch_and_store_media(
                        mock_media,
                        session,
                        attachments["audio"],
                        f"audio_{idx}.mp3",
                    )

    async def process_single_media(self, attachments, channel_post: Dict[str, Any]):
        async with ClientSession() as session:
            if "photo" in channel_post:
                photo_array = channel_post["photo"]
                file_id = photo_array[-1]["file_id"]
                mock_media = MockTelegramPhoto(file_id, self.token)
                await self.fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["images"],
                    "single_image.jpg",
                )
            elif "document" in channel_post:
                doc = channel_post["document"]
                file_id = doc["file_id"]
                file_name = doc.get("file_name", "single_document")
                mock_media = MockTelegramDocument(file_id, self.token)
                await self.fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["documents"],
                    file_name,
                )
            elif "video" in channel_post:
                vid = channel_post["video"]
                file_id = vid["file_id"]
                mock_media = MockTelegramVideo(file_id, self.token)
                await self.fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["videos"],
                    "single_video.mp4",
                )
            elif "audio" in channel_post:
                aud = channel_post["audio"]
                file_id = aud["file_id"]
                mock_media = MockTelegramAudio(file_id, self.token)
                await self.fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["audio"],
                    "single_audio.mp3",
                )


class MockTelegramPhoto:
    def __init__(self, file_id: str, token: str):
        self.file_id = file_id
        self.token = token

    async def get_file(self):
        return MockFilePath(self.file_id, self.token)


class MockTelegramDocument(MockTelegramPhoto):
    pass


class MockTelegramVideo(MockTelegramPhoto):
    pass


class MockTelegramAudio(MockTelegramPhoto):
    pass


class MockFilePath:
    def __init__(self, file_id: str, token: str):
        self.file_id = file_id
        self.file_path = self._get_file_path()
        self.url = f"https://api.telegram.org/bot{token}/getFile?file_id={self.file_id}"

    def _get_file_path(self) -> str:
        resp = requests.get(self.url)
        if resp.status_code == 200:
            result = resp.json()["result"]
            return result["file_path"]
        else:
            raise Exception(
                f"Failed to get file path for file_id={self.file_id}, status={resp.status_code}",
            )
