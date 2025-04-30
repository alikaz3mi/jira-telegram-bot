from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List

import aiohttp
import jdatetime
import requests
import uvicorn
from fastapi import FastAPI
from fastapi import Request

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.file_storage import load_data_store, save_data_store, save_mapping, \
    get_issue_key_from_channel_post, find_issue_key_from_message_id, find_group_chat_by_issue
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.services.telegram import MockTelegramPhoto, MockTelegramDocument, MockTelegramVideo, \
    MockTelegramAudio
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import send_telegram_message, fetch_and_store_media
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS
from jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue import parse_jira_prompt

app = FastAPI()

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
                if "h6. Comment from" in comment_content:
                    return {"status": "success", "message": "Webhook processed"}
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
        jira_repository.add_comment(issue_key, text)
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
    url = f"https://api.telegram.org/bot{TELEGRAM_SETTINGS.HOOK_TOKEN}/deleteWebhook"
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
    url = f"https://api.telegram.org/bot{TELEGRAM_SETTINGS.HOOK_TOKEN}/deleteWebhook"
    response = requests.get(url)
    if response.status_code == 200:
        LOGGER.info("Existing Telegram webhook deleted successfully.")
    else:
        LOGGER.error(f"Failed to delete existing Telegram webhook: {response.content}")
    url = f"https://api.telegram.org/bot{TELEGRAM_SETTINGS.HOOK_TOKEN}/setWebhook"
    payload = {
        "url": TELEGRAM_SETTINGS.WEBHOOK_URL,
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
