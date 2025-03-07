from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests
import uvicorn
from fastapi import FastAPI
from fastapi import Request

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.telegram.telegram_gateway import TelegramGateway
from jira_telegram_bot.adapters.telegram.telegram_utils import get_text_from_message
from jira_telegram_bot.adapters.telegram.telegram_utils import get_username_from_post
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_WEBHOOK_SETTINGS
from jira_telegram_bot.use_cases.prompts.ticket_issue_prompt import parse_jira_prompt
from jira_telegram_bot.utils.data_store import load_data_store

app = FastAPI()

TELEGRAM_BOT_TOKEN = TELEGRAM_WEBHOOK_SETTINGS.TOKEN
TELEGRAM_WEBHOOK_URL = TELEGRAM_SETTINGS.WEBHOOK_URL
JIRA_BASE_URL = JIRA_SETTINGS.domain
JIRA_PROJECT_KEY = "PCT"
jira_repository = JiraRepository(JIRA_SETTINGS)
telegram_gateway = TelegramGateway(TELEGRAM_WEBHOOK_SETTINGS)

users = {
    "alikaz3mi": "a_kazemi",
    "Mousavi_Shoushtari": "m_mousavi",
    "Alirezanasim_1991": "a_nasim",
    "davood_fazeli": "d_fazeli",
}

MEDIA_GROUP_STORE: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
MEDIA_GROUP_METADATA: Dict[str, float] = {}
GROUP_TIMEOUT_SECONDS = 5.0

DATA_STORE_PATH = f"{DEFAULT_PATH}/data_store.json"


async def process_media_group(messages: List[Dict[str, Any]], task_data: TaskData):
    """Process a group of media messages and create a Jira issue."""
    attachments = task_data.attachments
    await telegram_gateway.process_media_group(attachments, messages)

    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (media group) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
    LOGGER.info(issue_message)
    first_chat_id = messages[0]["chat"]["id"]
    telegram_gateway.send_telegram_message(first_chat_id, issue_message)

    channel_post_id = messages[0]["message_id"]
    save_mapping(channel_post_id, issue.key, messages[0]["chat"]["id"], first_chat_id)


async def process_single_message(channel_post: Dict[str, Any], task_data: TaskData):
    """Process a single message and create a Jira issue."""
    attachments = task_data.attachments
    await telegram_gateway.process_single_media(attachments, channel_post)

    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (single) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
    LOGGER.info(issue_message)
    chat_id = channel_post["chat"]["id"]
    telegram_gateway.send_telegram_message(chat_id, issue_message)

    channel_post_id = channel_post["message_id"]
    save_mapping(channel_post_id, issue.key, channel_post["chat"]["id"], chat_id)


def save_data_store(data: Dict[str, Any]):
    """Save the data store to the JSON file."""
    with open(DATA_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_mapping(channel_post_id: int, issue_key: str, chat_id: int, group_id: int):
    """Save the mapping between channel post and Jira issue."""
    data = load_data_store()
    data[str(channel_post_id)] = {
        "issue_key": issue_key,
        "channel_chat_id": chat_id,
        "group_chat_id": group_id,
    }
    save_data_store(data)


def get_issue_key_from_channel_post(channel_post_id: int) -> Optional[str]:
    """Retrieve the Jira issue key associated with a channel post."""
    data = load_data_store()
    return data.get(str(channel_post_id), {}).get("issue_key")


def get_group_chat_id_from_channel_post(channel_post_id: int) -> Optional[int]:
    """Retrieve the group chat ID associated with a channel post."""
    data = load_data_store()
    return data.get(str(channel_post_id), {}).get("group_chat_id")


async def add_comment_to_jira(issue_key: str, comment: str):
    """Add a comment to a Jira issue."""
    jira_repository.add_comment(issue_key, comment)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Main Telegram webhook: listens for channel posts or group messages,
    then creates or updates Jira tasks accordingly.
    """
    try:
        data = await request.json()
        LOGGER.debug(f"Incoming Telegram data: {data}")

        if "channel_post" in data:
            channel_post = data["channel_post"]
            username = get_username_from_post(channel_post)
            text = get_text_from_message(channel_post)

            parsed_fields = parse_jira_prompt(text)

            task_data = TaskData(
                project_key=JIRA_PROJECT_KEY,
                summary=parsed_fields["summary"],
                description=parsed_fields["description"],
                task_type=parsed_fields["task_type"],
                labels=[parsed_fields.get("labels", "")],
                assignee=users.get(username, None),
            )

            media_group_id = channel_post.get("media_group_id")
            if media_group_id:
                MEDIA_GROUP_STORE[media_group_id].append(channel_post)
                MEDIA_GROUP_METADATA[media_group_id] = time.time()
                LOGGER.info(
                    f"Stored media_group_id={media_group_id} update. "
                    f"Total so far: {len(MEDIA_GROUP_STORE[media_group_id])} messages.",
                )
                return {
                    "status": "success",
                    "message": "Media group update stored. Awaiting more.",
                }
            else:
                # Single message (text, or text+media)
                if any(
                    k in channel_post for k in ["photo", "video", "audio", "document"]
                ):
                    await process_single_message(channel_post, task_data)
                else:
                    # Just text
                    issue = jira_repository.create_task(task_data)
                    issue_message = (
                        f"Task created (text-only) successfully! "
                        f"Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
                    )
                    LOGGER.info(issue_message)
                    chat_id = channel_post["chat"]["id"]

                    # Save mapping
                    channel_post_id = channel_post["message_id"]
                    save_mapping(channel_post_id, issue.key, chat_id, chat_id)

                return {
                    "status": "success",
                    "message": "Single message processed, Jira created.",
                }

        # Handle messages in groups (comments)
        elif "message" in data:
            message = data["message"]
            if not message.get("is_automatic_forward", False):
                # Regular message in group => add comment
                chat_id = message["chat"]["id"]
                text = message.get("text") or message.get("caption") or ""

                # Find the related Jira issue based on group chat ID
                issue_key = None
                data_store = load_data_store()
                for mapping in data_store.values():
                    if mapping.get("group_chat_id") == chat_id:
                        issue_key = mapping.get("issue_key")
                        break
                if issue_key:
                    await add_comment_to_jira(issue_key, text)
                    LOGGER.info(f"Added comment to Jira issue {issue_key}: {text}")
                    return {
                        "status": "success",
                        "message": "Comment added to Jira issue.",
                    }
                else:
                    LOGGER.warning(
                        f"No Jira issue mapping found for group chat_id={chat_id}.",
                    )
                    return {
                        "status": "ignored",
                        "reason": "No Jira issue mapping found for this group.",
                    }
            else:
                # Handle automatic forward messages
                message_id = message["message_id"]
                forward_origin = message.get("forward_origin", {})
                original_message_id = forward_origin.get("message_id")
                issue_key = get_issue_key_from_channel_post(original_message_id)
                group_chat_id = message["chat"]["id"]

                if issue_key:
                    # Send message to the group
                    issue_link = f"{JIRA_SETTINGS.domain}/browse/{issue_key}"
                    issue_message = f"Jira Issue Created:\nLink: {issue_link}"
                    telegram_gateway.send_telegram_message(
                        group_chat_id,
                        issue_message,
                        reply_message_id=message_id,
                    )
                    data_local = load_data_store()
                    if str(original_message_id) in data_local:
                        data_local[str(original_message_id)][
                            "reply_message_id"
                        ] = message_id
                        save_data_store(data_local)
                    LOGGER.info(
                        f"Sent Jira issue link to group chat_id={group_chat_id}: {issue_link}",
                    )
                else:
                    LOGGER.warning(
                        f"No Jira issue found for original message_id={original_message_id}.",
                    )
                return {"status": "success", "message": "Forwarded message processed."}

        else:
            LOGGER.debug("Update does not contain channel_post or message.")
            return {"status": "ignored", "reason": "Unsupported update type."}

    except Exception as e:
        LOGGER.error(f"Error processing Telegram update: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.on_event("startup")
async def on_startup():
    set_telegram_webhook()
    await asyncio.create_task(finalize_media_groups())


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
    """Set the Telegram webhook."""
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
    """Finalize processing of media groups after a timeout."""
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

                parsed_fields = parse_jira_prompt(text)

                task_data = TaskData(
                    project_key=JIRA_PROJECT_KEY,
                    summary=parsed_fields["summary"],
                    description=text,
                    task_type=parsed_fields["task_type"],
                    assignee=users.get(username, None),
                )

                await process_media_group(messages, task_data)
            except Exception as e:
                LOGGER.error(
                    f"Error finalizing media_group_id={group_id}: {e}",
                    exc_info=True,
                )
        await asyncio.sleep(2.0)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2315)
