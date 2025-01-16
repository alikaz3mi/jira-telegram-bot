from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from io import BytesIO
from typing import Any
from typing import Dict
from typing import List

import aiohttp
import requests
import uvicorn
from fastapi import FastAPI
from fastapi import Request
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS


class JiraSettings(BaseSettings):
    base_url: str
    project_key: str
    email: str
    password: str
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app = FastAPI()

TELEGRAM_BOT_TOKEN = TELEGRAM_SETTINGS.TOKEN
TELEGRAM_WEBHOOK_URL = TELEGRAM_SETTINGS.WEBHOOK_URL
JIRA_BASE_URL = JIRA_SETTINGS.domain
JIRA_PROJECT_KEY = "CHATBUS"
jira_repository = JiraRepository(JIRA_SETTINGS)

users = {
    "alikaz3mi": "a_kazemi",
    "Mousavi_Shoushtari": "m_mousavi",
    "Alirezanasim_1991": "a_nasim",
    "davood_fazeli": "d_fazeli",
}

MEDIA_GROUP_STORE: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
MEDIA_GROUP_METADATA: Dict[str, float] = {}
GROUP_TIMEOUT_SECONDS = 5.0


def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        LOGGER.error(
            f"Failed to send Telegram message to chat_id={chat_id}: {resp.text}",
        )


class MockTelegramPhoto:
    def __init__(self, file_id):
        self.file_id = file_id

    async def get_file(self):
        return MockFilePath(self.file_id)


class MockTelegramDocument(MockTelegramPhoto):
    pass


class MockTelegramVideo(MockTelegramPhoto):
    pass


class MockTelegramAudio(MockTelegramPhoto):
    pass


class MockFilePath:
    def __init__(self, file_id):
        self.file_id = file_id
        self.file_path = self._get_file_path()

    def _get_file_path(self) -> str:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={self.file_id}"
        resp = requests.get(url)
        if resp.status_code == 200:
            result = resp.json()["result"]
            return result["file_path"]
        else:
            raise Exception(
                f"Failed to get file path for file_id={self.file_id}, status={resp.status_code}",
            )


async def fetch_and_store_media(
    media: Any,
    session: aiohttp.ClientSession,
    storage_list: List,
    filename: str,
):
    media_file = await media.get_file()
    file_url = (
        f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{media_file.file_path}"
    )
    async with session.get(file_url) as response:
        if response.status == 200:
            buffer = BytesIO(await response.read())
            storage_list.append((filename, buffer))
        else:
            LOGGER.error(
                f"Failed to fetch media: {media_file.file_path} (status {response.status})",
            )


async def process_media_group(messages: List[Dict[str, Any]], task_data: TaskData):
    attachments = task_data.attachments
    async with aiohttp.ClientSession() as session:
        for idx, msg in enumerate(messages):
            if "photo" in msg:
                photo_array = msg["photo"]
                file_info = photo_array[-1]
                file_id = file_info["file_id"]
                mock_media = MockTelegramPhoto(file_id)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["images"],
                    f"image_{idx}.jpg",
                )
            elif "document" in msg:
                doc = msg["document"]
                file_id = doc["file_id"]
                file_name = doc.get("file_name", f"document_{idx}")
                mock_media = MockTelegramDocument(file_id)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["documents"],
                    file_name,
                )
            elif "video" in msg:
                vid = msg["video"]
                file_id = vid["file_id"]
                mock_media = MockTelegramVideo(file_id)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["videos"],
                    f"video_{idx}.mp4",
                )
            elif "audio" in msg:
                aud = msg["audio"]
                file_id = aud["file_id"]
                mock_media = MockTelegramAudio(file_id)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["audio"],
                    f"audio_{idx}.mp3",
                )
    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (media group) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
    LOGGER.info(issue_message)
    first_chat_id = messages[0]["chat"]["id"]
    send_telegram_message(first_chat_id, issue_message)


async def process_single_message(channel_post: Dict[str, Any], task_data: TaskData):
    attachments = task_data.attachments
    async with aiohttp.ClientSession() as session:
        if "photo" in channel_post:
            photo_array = channel_post["photo"]
            file_id = photo_array[-1]["file_id"]
            mock_media = MockTelegramPhoto(file_id)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["images"],
                "single_image.jpg",
            )
        elif "document" in channel_post:
            doc = channel_post["document"]
            file_id = doc["file_id"]
            file_name = doc.get("file_name", "single_document")
            mock_media = MockTelegramDocument(file_id)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["documents"],
                file_name,
            )
        elif "video" in channel_post:
            vid = channel_post["video"]
            file_id = vid["file_id"]
            mock_media = MockTelegramVideo(file_id)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["videos"],
                "single_video.mp4",
            )
        elif "audio" in channel_post:
            aud = channel_post["audio"]
            file_id = aud["file_id"]
            mock_media = MockTelegramAudio(file_id)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["audio"],
                "single_audio.mp3",
            )
    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (single) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
    LOGGER.info(issue_message)
    chat_id = channel_post["chat"]["id"]
    send_telegram_message(chat_id, issue_message)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        LOGGER.debug(f"Incoming Telegram data: {data}")
        if "channel_post" not in data:
            return {"status": "ignored", "reason": "Not a channel_post update"}
        channel_post = data["channel_post"]
        username = channel_post.get("from", {}).get("username", "UnknownUser")
        text = channel_post.get("text") or channel_post.get("caption") or ""
        lines = text.strip().split("\n")
        task_data = TaskData()
        task_data.project_key = JIRA_PROJECT_KEY
        task_data.summary = lines[0] if lines else "No Summary"
        task_data.description = text or "No description provided."
        task_data.task_type = "Task" if "bug" not in text.lower() else "Bug"
        task_data.assignee = users.get(username, None)
        media_group_id = channel_post.get("media_group_id")
        if media_group_id:
            MEDIA_GROUP_STORE[media_group_id].append(channel_post)
            MEDIA_GROUP_METADATA[media_group_id] = time.time()
            LOGGER.info(
                f"Stored media_group_id={media_group_id} update. Total so far: {len(MEDIA_GROUP_STORE[media_group_id])} messages.",
            )
            return {
                "status": "success",
                "message": "Media group update stored. Awaiting more.",
            }
        else:
            if any(k in channel_post for k in ["photo", "video", "audio", "document"]):
                await process_single_message(channel_post, task_data)
            else:
                issue = jira_repository.create_task(task_data)
                issue_message = f"Task created (text-only) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
                LOGGER.info(issue_message)
                chat_id = channel_post["chat"]["id"]
                send_telegram_message(chat_id, issue_message)
            return {
                "status": "success",
                "message": "Single message processed, Jira created.",
            }
    except Exception as e:
        LOGGER.error(f"Error processing Telegram update: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.on_event("startup")
async def on_startup():
    set_telegram_webhook()
    asyncio.create_task(finalize_media_groups())


@app.on_event("shutdown")
async def on_shutdown():
    LOGGER.info("Shutting down...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    response = requests.get(url)
    if response.status_code == 200:
        LOGGER.info("Telegram webhook deleted successfully.")
    else:
        LOGGER.error(f"Failed to delete Telegram webhook: {response.content}")


def set_telegram_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        "url": TELEGRAM_WEBHOOK_URL,
        "max_connections": 100,
        "drop_pending_updates": True,
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        LOGGER.info("Telegram webhook set successfully.")
    else:
        LOGGER.error(f"Failed to set Telegram webhook: {response.content}")


async def finalize_media_groups():
    while True:
        now = time.time()
        to_finalize = []
        for group_id, last_update_time in list(MEDIA_GROUP_METADATA.items()):
            if now - last_update_time >= GROUP_TIMEOUT_SECONDS:
                to_finalize.append(group_id)
        for group_id in to_finalize:
            try:
                messages = MEDIA_GROUP_STORE.pop(group_id, [])
                MEDIA_GROUP_METADATA.pop(group_id, None)
                if not messages:
                    continue
                first_message = messages[0]
                username = first_message.get("from", {}).get("username", "UnknownUser")
                text = first_message.get("text") or first_message.get("caption") or ""
                lines = text.strip().split("\n")
                task_data = TaskData()
                task_data.project_key = JIRA_PROJECT_KEY
                task_data.summary = lines[0] if lines else "No Summary"
                task_data.description = text or "No description provided."
                task_data.task_type = "Task" if "bug" not in text.lower() else "Bug"
                task_data.assignee = users.get(username, None)
                await process_media_group(messages, task_data)
            except Exception as e:
                LOGGER.error(
                    f"Error finalizing media_group_id={group_id}: {e}",
                    exc_info=True,
                )
        await asyncio.sleep(2.0)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2315)
