from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict
from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import aiohttp
import jdatetime
import requests
import uvicorn
from fastapi import FastAPI
from fastapi import Request
from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS


def parse_jira_prompt(content: str) -> Dict[str, str]:
    """
    Uses a LangChain LLM prompt to parse the content and produce a JSON string
    with 'summary', 'task_type', and 'description'. Then returns it as a dict.
    """

    schema = [
        ResponseSchema(
            name="task_info",
            description="A JSON object containing summary, task_type, label, and description fields. Example: {'summary': 'Task summary', 'task_type': 'Bug', 'description': 'Task description', 'label': '#ID121'}",
            type="json",
        ),
    ]

    parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = parser.get_format_instructions()

    template_text = """
                    You are given the following content from a user:

                    {content}

                    Your job is to analyze this content and provide structured output for creating a task for jira.
                    keep the same language as the content.


                    {format_instructions}

                    Instructions:
                    1. "task_type": The type of task must only be Task or Bug.
                    2. "summary": the summary must be a single line. with the same language as content. If exists in content, keep #ID number in the summary.
                    3. "description": the description must be a single line. with the same language as content.
                    4. "label": label is the #ID if the content has it.
                    """

    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        openai_api_key=OPENAI_SETTINGS.token,
        temperature=0.2,
    )
    prompt = PromptTemplate(
        template=template_text,
        input_variables=["content"],
        partial_variables={"format_instructions": format_instructions},
    )

    chain = prompt | llm | parser

    result = chain.invoke(input={"content": content})

    try:
        return {
            "summary": result["task_info"].get("summary", ""),
            "task_type": result["task_info"].get("task_type", "Task"),
            "description": result["task_info"].get("description", ""),
            "labels": result["task_info"].get("label", ""),
        }
    except Exception as e:
        return {
            "summary": "No Summary",
            "task_type": "Task",
            "description": content or "No description provided.",
        }


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

TELEGRAM_BOT_TOKEN = "7601757345:AAFFbCKqIlLWMWcQn3HGstGWlClJmw-YtkU"
TELEGRAM_WEBHOOK_URL = TELEGRAM_SETTINGS.WEBHOOK_URL
JIRA_BASE_URL = JIRA_SETTINGS.domain
JIRA_PROJECT_KEY = "PCT"
jira_repository = JiraRepository(JIRA_SETTINGS)

users = {
    "alikaz3mi": "a_kazemi",
    "Mousavi_Shoushtari": "m_mousavi",
    "Alirezanasim_1991": "a_nasim",
    "GroupAnonymousBot": "a_kazemi",
    "Abolfazl2883": "a_barghamadi",
    "Parschat_AI": "sh_zanganeh",
}

jira_users = {
    "a_kazemi": "alikaz3mi",
    "m_mousavi": "Mousavi_Shoushtari",
    "a_nasim": "Alirezanasim_1991",
    "a_barghamadi": "Abolfazl2883",
    "sh_zanganeh": "Parschat_AI",
}

MEDIA_GROUP_STORE: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
MEDIA_GROUP_METADATA: Dict[str, float] = {}
GROUP_TIMEOUT_SECONDS = 5.0

DATA_STORE_PATH = f"{DEFAULT_PATH}/data_store.json"


def send_telegram_message(
    chat_id: int,
    text: str,
    reply_message_id: Optional[int] = None,
    parse_mode: str = "Markdown",
):
    """Send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_message_id:
        payload["reply_parameters"] = {"message_id": reply_message_id}
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
    """Fetch media from Telegram and store it in the provided storage list."""
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
    """Process a group of media messages and create a Jira issue."""
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
    post = load_data_store()[str(messages[-1]["message_id"])]
    group_chat_id = post["group_chat_id"]
    data_store = load_data_store()
    for message in messages:
        if str(message["message_id"]) in data_store:
            data_store[str(message["message_id"])]["issue_key"] = issue.key
            data_store[str(message["message_id"])]["reply_message_id"] = message[
                "message_id"
            ]
            save_data_store(data_store)
    send_telegram_message(
        group_chat_id,
        issue_message,
        reply_message_id=post["reply_message_id"],
    )


async def process_single_message(channel_post: Dict[str, Any], task_data: TaskData):
    """Process a single message and create a Jira issue."""
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

    channel_post_id = channel_post["message_id"]
    await save_mapping(
        channel_post_id,
        issue.key,
        channel_post["chat"]["id"],
        chat_id,
        message_data=channel_post,
    )


def load_data_store() -> Dict[str, Any]:
    """Load the data store from the JSON file."""
    if not os.path.exists(DATA_STORE_PATH):
        return {}
    with open(DATA_STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data_store(data: Dict[str, Any]):
    """Save the data store to the JSON file."""
    with open(DATA_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


async def save_mapping(
    channel_post_id: int,
    issue_key: str,
    channel_chat_id: int,
    group_id: int,
    message_data: Dict[str, Any],
):
    """Save the mapping between channel post and Jira issue with additional metadata.

    Args:
        channel_post_id: The ID of the post in the channel
        issue_key: The Jira issue key (e.g. PCT-123)
        channel_chat_id: ID of the channel where message was posted
        group_id: ID of the group where the message was forwarded
        message_data: The full message data containing metadata
    """
    data = load_data_store()

    # Extract additional metadata
    created_at = message_data.get("date", int(time.time()))  # Fallback to current time
    from_user = message_data.get("from", {})
    message_type = "channel_post"

    # Media type detection
    if "photo" in message_data:
        content_type = "photo"
    elif "video" in message_data:
        content_type = "video"
    elif "document" in message_data:
        content_type = "document"
    elif "audio" in message_data:
        content_type = "audio"
    else:
        content_type = "text"

    data[str(channel_post_id)] = {
        "type": "jira_issue_mapping",
        "issue_key": issue_key,
        "channel_chat_id": channel_chat_id,
        "group_chat_id": group_id,
        "metadata": {
            "created_at": created_at,
            "creator_id": from_user.get("id"),
            "creator_username": from_user.get("username"),
            "content_type": content_type,
            "message_type": message_type,
        },
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


@app.post("/jira-webhook")
async def jira_webhook_endpoint(request: Request):
    """
    FastAPI endpoint receiving Jira webhook events.
    Handles state transitions and due date changes.
    """
    try:
        body = await request.json()

        # Get the relevant data from the webhook
        issue_key = body.get("issue", {}).get("key")
        if not issue_key:
            return {"status": "error", "message": "No issue key found in webhook data"}

        # Load the data store to find the associated group chat
        data_store = load_data_store()
        group_chat_info = find_group_chat_by_issue(data_store, issue_key)

        if not group_chat_info:
            LOGGER.warning(f"No group chat mapping found for issue {issue_key}")
            return {"status": "ignored", "message": "No group chat mapping found"}

        group_chat_id = group_chat_info["group_chat_id"]

        issue_commented = body.get("issue_event_type_name", {})
        if issue_commented == "issue_commented":
            comment = body.get("comment", {})
            if comment:
                comment_body = comment.get("body", "")
                username = comment.get("author", {}).get("name", "UnknownUser")
                username = jira_users.get(username, username)
                comment_content = f"Comment from [@{username}] :\n\n{comment_body}"
                message = f"*💬 Comment Added*\n\nTask {issue_key} has a new comment: {comment_content}"
                send_telegram_message(
                    group_chat_id,
                    message,
                    reply_message_id=group_chat_info["reply_message_id"],
                )
                LOGGER.info(f"Sent comment notification for {issue_key}")

        # Handle status transition
        changelog = body.get("changelog", {}).get("items", [])
        for item in changelog:
            if item.get("field") == "status":
                old_status = item.get("fromString")
                new_status = item.get("toString")
                message = f"*📊 Status Update *\n\nTask {issue_key} moved from *'{old_status}'* to *'{new_status}'*"
                send_telegram_message(
                    group_chat_id,
                    message,
                    reply_message_id=group_chat_info["reply_message_id"],
                )
                LOGGER.info(f"Sent status transition notification for {issue_key}")
                if new_status == "Review":
                    creator_username = group_chat_info.get("metadata", {}).get(
                        "creator_username",
                    )
                    if creator_username and creator_username in users:
                        assignee = users[creator_username]
                        jira_repository.assign_issue(issue_key, assignee)
                        notify_msg = f"*👤 Task Reassigned*\n\nTask {issue_key} has been assigned to @{creator_username} for review"
                        send_telegram_message(
                            group_chat_id,
                            notify_msg,
                            reply_message_id=group_chat_info["reply_message_id"],
                        )
                        LOGGER.info(f"Reassigned {issue_key} to {assignee} for review")

            elif item.get("field") == "duedate":
                old_date = item.get("fromString", "not set")
                new_date = item.get("toString", "not set")
                year, month, day = new_date.split(" ")[0].split("-")
                time = new_date.split(" ")[1]
                georgian_time = jdatetime.GregorianToJalali(
                    int(year),
                    int(month),
                    int(day),
                )
                new_date = f"{georgian_time.jyear}/{georgian_time.jmonth}/{georgian_time.jday} {time}"
                if new_date != "not set":
                    message = (
                        f"*📅 Due Date Set*\n\nTask {issue_key} is due on *{new_date}*"
                    )
                elif old_date != "not set":
                    old_date = old_date.split(" ")[0]
                    year, month, day = old_date.split("-")
                    georgian_time = jdatetime.GregorianToJalali(
                        int(year),
                        int(month),
                        int(day),
                    )
                    old_date = f"{georgian_time.jyear}/{georgian_time.jmonth}/{georgian_time.jday}"
                    message = f"*📅 Due Date Removed*\n\nTask {issue_key} due date has been cleared (was: {old_date})"
                else:
                    message = f"*📅 Due Date Cleared*\n\nTask {issue_key} due date has been cleared"
                # Send the message to the group chat
                send_telegram_message(
                    group_chat_id,
                    message,
                    reply_message_id=group_chat_info["reply_message_id"],
                )
                LOGGER.info(f"Sent due date update notification for {issue_key}")
            elif item.get("field") == "due date":
                old_date = item.get("from", "not set")
                new_date = item.get("to", "not set")
                year, month, day = new_date.split("T")[0].split("-")
                time = item.get("toString", "not set").split(" ", 1)[1]
                georgian_time = jdatetime.GregorianToJalali(
                    int(year),
                    int(month),
                    int(day),
                )
                new_date = f"{georgian_time.jyear}/{georgian_time.jmonth}/{georgian_time.jday} {time}"
                if new_date != "not set":
                    message = (
                        f"*📅 Due Date Set*\n\nTask {issue_key} is due on *{new_date}*"
                    )
                elif old_date != "not set":
                    old_date = old_date.split(" ")[0]
                    year, month, day = old_date.split("-")
                    georgian_time = jdatetime.GregorianToJalali(
                        int(year),
                        int(month),
                        int(day),
                    )
                    old_date = f"{georgian_time.jyear}/{georgian_time.jmonth}/{georgian_time.jday}"
                    message = f"*📅 Due Date Removed*\n\nTask {issue_key} due date has been cleared (was: {old_date})"
                else:
                    message = f"*📅 Due Date Cleared*\n\nTask {issue_key} due date has been cleared"
                # Send the message to the group chat
                send_telegram_message(
                    group_chat_id,
                    message,
                    reply_message_id=group_chat_info["reply_message_id"],
                )
                LOGGER.info(f"Sent due date update notification for {issue_key}")

        return {"status": "success", "message": "Webhook processed"}

    except Exception as e:
        LOGGER.error(f"Error processing Jira webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def find_group_chat_by_issue(
    data_store: Dict[str, Any],
    issue_key: str,
) -> Optional[Dict[str, Any]]:
    """Find the group chat info for a given issue key."""
    for entry in data_store.values():
        if entry.get("issue_key") == issue_key:
            return entry
    return None


async def handle_channel_post(channel_post: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming channel posts."""
    username = channel_post.get("from", {}).get("username", "UnknownUser")
    text = channel_post.get("text") or channel_post.get("caption") or ""

    parsed_fields = parse_jira_prompt(text)
    task_data = create_task_data(username, parsed_fields)

    media_group_id = channel_post.get("media_group_id")
    if media_group_id:
        return await handle_media_group_message(media_group_id, channel_post)
    else:
        return await handle_single_message(channel_post, task_data)


async def handle_media_group_message(
    media_group_id: str,
    channel_post: Dict[str, Any],
) -> Dict[str, Any]:
    """Handle messages that are part of a media group."""
    MEDIA_GROUP_STORE[media_group_id].append(channel_post)
    MEDIA_GROUP_METADATA[media_group_id] = time.time()
    LOGGER.info(
        f"Stored media_group_id={media_group_id} update. Total so far: {len(MEDIA_GROUP_STORE[media_group_id])} messages.",
    )
    for message in MEDIA_GROUP_STORE[media_group_id]:
        await save_mapping(
            message["message_id"],
            "pending",  # Will be updated when issue is created
            message["chat"]["id"],
            message["chat"]["id"],
            message_data=message,
        )
    return {
        "status": "success",
        "message": "Media group update stored. Awaiting more.",
    }


async def handle_single_message(
    channel_post: Dict[str, Any],
    task_data: TaskData,
) -> Dict[str, Any]:
    """Handle single messages (with or without media)."""
    if any(k in channel_post for k in ["photo", "video", "audio", "document"]):
        await process_single_message(channel_post, task_data)
    else:
        await process_text_only_message(channel_post, task_data)

    return {
        "status": "success",
        "message": "Single message processed, Jira created.",
    }


async def process_text_only_message(
    channel_post: Dict[str, Any],
    task_data: TaskData,
) -> None:
    """Process text-only messages."""
    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (text-only) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
    LOGGER.info(issue_message)
    chat_id = channel_post["chat"]["id"]

    channel_post_id = channel_post["message_id"]
    await save_mapping(
        channel_post_id,
        issue.key,
        chat_id,
        chat_id,
        message_data=channel_post,
    )
    # send_telegram_message(chat_id, issue_message)


async def handle_group_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle messages in group chats."""
    if message.get("is_automatic_forward", False) is True:
        return await handle_auto_forward_message(message)
    else:
        return await handle_group_comment(message)


async def handle_auto_forward_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle automatically forwarded messages from channel to group."""
    message_id = message["message_id"]
    forward_origin = message.get("forward_origin", {})
    original_message_id = forward_origin.get("message_id")
    issue_key = get_issue_key_from_channel_post(original_message_id)
    group_chat_id = message["chat"]["id"]

    if issue_key:
        issue_link = f"{JIRA_SETTINGS.domain}/browse/{issue_key}"
        issue_message = f"Jira Issue Created:\nLink: {issue_link}"
        if issue_key != "pending":
            send_telegram_message(
                group_chat_id,
                issue_message,
                reply_message_id=message_id,
            )

        data_local = load_data_store()
        if str(original_message_id) in data_local:
            entry = data_local[str(original_message_id)]
            entry["group_chat_id"] = group_chat_id
            entry["metadata"]["forwarded_at"] = int(time.time())
            entry["reply_message_id"] = message_id
            save_data_store(data_local)

        LOGGER.info(
            f"Sent Jira issue link to group chat_id={group_chat_id}: {issue_link}",
        )
        return {"status": "success", "message": "Forwarded message processed."}
    else:
        LOGGER.warning(
            f"No Jira issue found for original message_id={original_message_id}",
        )
        return {"status": "error", "message": "No matching Jira issue found"}


async def handle_group_comment(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle comments in group chats."""
    chat_id = message["chat"]["id"]
    message_from = message.get("from", {}).get("username", "UnknownUser")
    username = users.get(message_from, None)
    text = message.get("text") or message.get("caption") or ""
    text = f"h6. Comment from [~{username}] :\n\n{text}"

    issue_key = find_issue_key_from_message_id(
        f"{message['reply_to_message']['forward_from_message_id']}",
    )
    if issue_key:
        await add_comment_to_jira(issue_key, text)
        LOGGER.info(f"Added comment to Jira issue {issue_key}: {text}")
        return {
            "status": "success",
            "message": "Comment added to Jira issue.",
        }
    else:
        LOGGER.warning(f"No Jira issue mapping found for group chat_id={chat_id}")
        return {
            "status": "ignored",
            "reason": "No Jira issue mapping found for this group.",
        }


def find_issue_key_for_group(chat_id: int) -> Optional[str]:
    """Find the Jira issue key associated with a group chat."""
    data_store = load_data_store()
    for mapping in data_store.values():
        if mapping.get("group_chat_id") == chat_id:
            return mapping.get("issue_key")
    return None


def find_issue_key_from_message_id(message_id: int) -> Optional[str]:
    """Find the Jira issue key associated with a message ID."""
    data_store = load_data_store()
    return data_store.get(str(message_id), {}).get("issue_key")


def create_task_data(username: str, parsed_fields: Dict[str, str]) -> TaskData:
    """Create TaskData object from parsed fields."""
    return TaskData(
        project_key=JIRA_PROJECT_KEY,
        summary=parsed_fields["summary"],
        description=parsed_fields["description"],
        task_type=parsed_fields["task_type"],
        labels=[parsed_fields.get("labels", "")],
        assignee=users.get(username, None),
    )


async def handle_webhook_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle different types of Telegram updates."""
    LOGGER.debug(f"Processing Telegram update: {data}")

    if "channel_post" in data:
        LOGGER.info(
            f"Handling channel post with ID: {data['channel_post'].get('message_id')}",
        )
        return await handle_channel_post(data["channel_post"])
    elif "message" in data:
        LOGGER.info(
            f"Handling group message with ID: {data['message'].get('message_id')}",
        )
        return await handle_group_message(data["message"])

    LOGGER.warning("Update does not contain channel_post or message")
    return {"status": "ignored", "reason": "Unsupported update type."}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Main Telegram webhook handler."""
    try:
        data = await request.json()
        return await handle_webhook_update(data)
    except Exception as e:
        LOGGER.error(f"Error processing Telegram update: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.on_event("startup")
async def on_startup():
    """Initialize webhook and start background tasks on application startup."""
    set_telegram_webhook()
    asyncio.create_task(finalize_media_groups())


@app.on_event("shutdown")
async def on_shutdown():
    """Clean up on application shutdown."""
    LOGGER.info("Shutting down application...")
    await remove_telegram_webhook()


async def remove_telegram_webhook():
    """Remove the Telegram webhook."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                LOGGER.info("Telegram webhook deleted successfully")
            else:
                LOGGER.error(
                    f"Failed to delete Telegram webhook: {await response.text()}",
                )


def set_telegram_webhook():
    """Set the Telegram webhook."""
    # Delete webhook if it exists
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    response = requests.get(url)
    if response.status_code == 200:
        LOGGER.info("Existing Telegram webhook deleted successfully.")
    else:
        LOGGER.error(f"Failed to delete existing Telegram webhook: {response.content}")
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

                # Use LangChain to parse the text
                parsed_fields = parse_jira_prompt(text)

                task_data = TaskData(
                    project_key=JIRA_PROJECT_KEY,
                    summary=parsed_fields["summary"],
                    description=parsed_fields["description"],
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
