from __future__ import annotations

# MIGRATION NOTICE:
# ================
# This file contains legacy FastAPI code that violates Clean Architecture principles.
# It should be gradually migrated to proper use cases in jira_telegram_bot/use_cases/
# and endpoints in jira_telegram_bot/frameworks/api/endpoints/
# 
# The new Clean Architecture API server is in jira_telegram_bot/frameworks/api/main.py
# 
# TODO: Extract business logic to use cases:
# - Jira webhook processing with comment handling, status changes, etc.
# - Telegram webhook processing with media group handling
# - Channel post processing and task creation
# - Group message handling and auto-forwarding
#
# IMPORTANT: This file is currently used in production. Migration should be done gradually.

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

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.file_storage import TelegramPostDataStore
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)
from jira_telegram_bot.adapters.services.telegram import MockTelegramAudio
from jira_telegram_bot.adapters.services.telegram import MockTelegramDocument
from jira_telegram_bot.adapters.services.telegram import MockTelegramPhoto
from jira_telegram_bot.adapters.services.telegram import MockTelegramVideo
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import (
    fetch_and_store_media,
)
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import (
    send_telegram_message,
)
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue import (
    parse_jira_prompt,
)


JIRA_SETTINGS = JiraConnectionSettings()
TELEGRAM_SETTINGS = TelegramConnectionSettings()
app = FastAPI()
telegram_post_data_store = TelegramPostDataStore()
jira_repository = JiraServerRepository(JIRA_SETTINGS)
user_config = UserConfig()

JIRA_PROJECT_KEY = "PCT"
MEDIA_GROUP_STORE: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
MEDIA_GROUP_METADATA: Dict[str, float] = {}
GROUP_TIMEOUT_SECONDS = 5.0


async def process_media_group(messages: List[Dict[str, Any]], task_data: TaskData):
    """Process a group of media messages and create a Jira issue."""
    attachments = task_data.attachments
    async with aiohttp.ClientSession() as session:
        for idx, msg in enumerate(messages):
            if "photo" in msg:
                photo_array = msg["photo"]
                file_info = photo_array[-1]
                file_id = file_info["file_id"]
                mock_media = MockTelegramPhoto(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["images"],
                    f"image_{idx}.jpg",
                    token=TELEGRAM_SETTINGS.HOOK_TOKEN,
                )
            elif "document" in msg:
                doc = msg["document"]
                file_id = doc["file_id"]
                file_name = doc.get("file_name", f"document_{idx}")
                mock_media = MockTelegramDocument(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["documents"],
                    file_name,
                    token=TELEGRAM_SETTINGS.HOOK_TOKEN,
                )
            elif "video" in msg:
                vid = msg["video"]
                file_id = vid["file_id"]
                mock_media = MockTelegramVideo(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["videos"],
                    f"video_{idx}.mp4",
                    token=TELEGRAM_SETTINGS.HOOK_TOKEN,
                )
            elif "audio" in msg:
                aud = msg["audio"]
                file_id = aud["file_id"]
                mock_media = MockTelegramAudio(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                await fetch_and_store_media(
                    mock_media,
                    session,
                    attachments["audio"],
                    f"audio_{idx}.mp3",
                    token=TELEGRAM_SETTINGS.HOOK_TOKEN,
                )

    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (media group) successfully! Link: {JIRA_SETTINGS.domain.scheme}://{JIRA_SETTINGS.domain.host}/browse/{issue.key}"
    LOGGER.info(issue_message)
    
    # Update issue_key in data store for all messages in the group
    data_store = telegram_post_data_store.load_data_store()
    for message in messages:
        if str(message["message_id"]) in data_store:
            data_store[str(message["message_id"])]["issue_key"] = issue.key
    telegram_post_data_store.save_data_store(data_store)
    
    # Wait for auto-forward to update group_chat_id (retry with timeout)
    max_retries = 10
    retry_delay = 1.0  # seconds
    group_chat_id = None
    reply_message_id = None
    channel_chat_id = messages[0]["chat"]["id"]
    
    for attempt in range(max_retries):
        data_store = telegram_post_data_store.load_data_store()
        post = data_store.get(str(messages[-1]["message_id"]), {})
        potential_group_id = post.get("group_chat_id")
        
        # Check if group_chat_id is different from channel_chat_id (meaning it was updated)
        if potential_group_id and potential_group_id != channel_chat_id:
            group_chat_id = potential_group_id
            reply_message_id = post.get("reply_message_id")
            LOGGER.info(f"Found group_chat_id={group_chat_id} for media group after {attempt + 1} attempts")
            break
        
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)
    
    # Send message to group if we found the group_chat_id
    if group_chat_id and reply_message_id:
        send_telegram_message(
            group_chat_id,
            issue_message,
            reply_message_id=reply_message_id,
            token=TELEGRAM_SETTINGS.HOOK_TOKEN
        )
    else:
        LOGGER.warning(
            f"Could not send Jira link for media group {issue.key} - group_chat_id not found after {max_retries} attempts"
        )


async def process_single_message(channel_post: Dict[str, Any], task_data: TaskData):
    """Process a single message and create a Jira issue."""
    attachments = task_data.attachments
    async with aiohttp.ClientSession() as session:
        if "photo" in channel_post:
            photo_array = channel_post["photo"]
            file_id = photo_array[-1]["file_id"]
            mock_media = MockTelegramPhoto(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["images"],
                "single_image.jpg",
                token=TELEGRAM_SETTINGS.HOOK_TOKEN,
            )
        elif "document" in channel_post:
            doc = channel_post["document"]
            file_id = doc["file_id"]
            file_name = doc.get("file_name", "single_document")
            mock_media = MockTelegramDocument(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["documents"],
                file_name,
                token=TELEGRAM_SETTINGS.HOOK_TOKEN,
            )
        elif "video" in channel_post:
            vid = channel_post["video"]
            file_id = vid["file_id"]
            mock_media = MockTelegramVideo(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["videos"],
                "single_video.mp4",
                token=TELEGRAM_SETTINGS.HOOK_TOKEN,
            )
        elif "audio" in channel_post:
            aud = channel_post["audio"]
            file_id = aud["file_id"]
            mock_media = MockTelegramAudio(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            await fetch_and_store_media(
                mock_media,
                session,
                attachments["audio"],
                "single_audio.mp3",
                token=TELEGRAM_SETTINGS.HOOK_TOKEN,
            )

    issue = jira_repository.create_task(task_data)
    issue_message = f"Task created (single) successfully! Link: {JIRA_SETTINGS.domain}/browse/{issue.key}"
    LOGGER.info(issue_message)
    chat_id = channel_post["chat"]["id"]

    channel_post_id = channel_post["message_id"]
    await telegram_post_data_store.save_mapping(
        channel_post_id,
        issue.key,
        channel_post["chat"]["id"],
        chat_id,
        message_data=channel_post,
    )


async def handle_comment_event(
    body: Dict[str, Any],
    group_chat_id: str,
    reply_message_id: int,
    issue_key: str,
) -> None:
    """Handle a new comment event from Jira webhook."""
    comment = body.get("comment", {})
    if not comment:
        return

    comment_body = comment.get("body", "")
    jira_username = comment.get("author", {}).get("name", "UnknownUser")
    telegram_username = user_config.get_user_config_by_jira_username(
        jira_username,
    ).telegram_username

    # Skip if this is a comment we posted from Telegram
    if "h6. Comment from" in comment_body:
        return

    comment_content = f"Comment from [@{telegram_username}] :\n\n{comment_body}"
    message = (
        f"*💬 Comment Added*\n\nTask {issue_key} has a new comment: {comment_content}"
    )
    send_telegram_message(
        group_chat_id,
        message,
        reply_message_id=reply_message_id,
        token=TELEGRAM_SETTINGS.HOOK_TOKEN
    )
    LOGGER.info(f"Sent comment notification for {issue_key}")


async def handle_status_change(
    item: Dict[str, Any],
    issue_key: str,
    group_chat_id: str,
    reply_message_id: int,
    user_data: Dict[str, Any],
) -> None:
    """Handle a status change event from Jira webhook."""
    old_status = item.get("fromString")
    new_status = item.get("toString")
    message = f"*📊 Status Update *\n\nTask {issue_key} moved from *'{old_status}'* to *'{new_status}'*"
    send_telegram_message(
        group_chat_id,
        message,
        reply_message_id=reply_message_id,
        token=TELEGRAM_SETTINGS.HOOK_TOKEN
    )
    LOGGER.info(f"Sent status transition notification for {issue_key}")

    if new_status == "Review":
        await handle_review_transition(
            issue_key,
            group_chat_id,
            reply_message_id,
            user_data,
        )


async def handle_review_transition(
    issue_key: str,
    group_chat_id: str,
    reply_message_id: int,
    user_data: Dict[str, Any],
) -> None:
    """Handle transition to review status."""
    creator_username = user_data.get("metadata", {}).get("creator_username")
    if not creator_username or creator_username not in user_config.list_all_users():
        return

    user_cfg = user_config.get_user_config(creator_username)
    assignee = user_cfg.jira_username if user_cfg else None
    if not assignee:
        LOGGER.warning(f"No jira_username found for creator: {creator_username}")
        return
        
    jira_repository.assign_issue(issue_key, assignee)
    notify_msg = f"""*👤 Task Reassigned*\n\nTask {issue_key} has been assigned to @{creator_username} for review"""
    send_telegram_message(
        group_chat_id,
        notify_msg,
        reply_message_id=reply_message_id,
        token=TELEGRAM_SETTINGS.HOOK_TOKEN
    )
    LOGGER.info(f"Reassigned {issue_key} to {assignee} for review")


async def handle_due_date_change(
    item: Dict[str, Any],
    issue_key: str,
    group_chat_id: str,
    reply_message_id: int,
) -> None:
    """Handle a due date change event from Jira webhook."""
    old_date = item.get("fromString", "not set")
    new_date = item.get("toString", "not set")

    if new_date != "not set":
        formatted_date = format_jalali_date(new_date)
        message = f"*📅 Due Date Set*\n\nTask {issue_key} is due on *{formatted_date}*"
    elif old_date != "not set":
        formatted_old_date = format_jalali_date(old_date.split(" ")[0])
        message = f"*📅 Due Date Removed*\n\nTask {issue_key} due date has been cleared (was: {formatted_old_date})"
    else:
        message = f"*📅 Due Date Cleared*\n\nTask {issue_key} due date has been cleared"

    send_telegram_message(
        group_chat_id,
        message,
        reply_message_id=reply_message_id,
        token=TELEGRAM_SETTINGS.HOOK_TOKEN
    )
    LOGGER.info(f"Sent due date update notification for {issue_key}")


def format_jalali_date(date_str: str) -> str:
    try:
        """Convert a Gregorian date string to Jalali format."""
        if " " not in date_str:
            date_str += " 00:00"
        year, month, day = date_str.split(" ")[0].split("-")
        time = date_str.split(" ")[1]
        georgian_time = jdatetime.GregorianToJalali(
            int(year),
            int(month),
            int(day),
        )
        return f"{georgian_time.jyear}/{georgian_time.jmonth}/{georgian_time.jday} {time}"
    except Exception as e:
        LOGGER.error(f"Error formatting date {date_str}: {e}")
        return date_str


async def process_command(
    text: str,
    issue_key: str,
    message_from: str,
    jira_username: str,
) -> Dict[str, Any]:
    """Process command messages in group chat."""
    data_store = telegram_post_data_store.load_data_store()
    store_entry = telegram_post_data_store.find_channel_post_by_issue(data_store, issue_key)
    if "/done" in text.lower():
        if (
            store_entry
            and store_entry.get("metadata", {}).get("creator_username") == message_from
        ):
            jira_repository.transition_task(issue_key, "done")
            store_entry["resolved_at"] = int(time.time())
            telegram_post_data_store.save_data_store(data_store)
            send_telegram_message(
                store_entry["group_chat_id"],
                f"Task {issue_key} marked as Done",
                reply_message_id=store_entry["reply_message_id"],
                token=TELEGRAM_SETTINGS.HOOK_TOKEN
            )

            return {"status": "success", "message": f"Task {issue_key} marked as done"}

    elif "/review" in text.lower():
        issue = jira_repository.jira.issue(issue_key)
        if issue.fields.assignee and issue.fields.assignee.name == jira_username:
            jira_repository.transition_task(issue_key, "review")
            send_telegram_message(
                store_entry["group_chat_id"],
                f"Task {issue_key} marked as Review",
                reply_message_id=store_entry["reply_message_id"],
                token=TELEGRAM_SETTINGS.HOOK_TOKEN
            )
            return {"status": "success", "message": f"Task {issue_key} moved to review"}

    return None


@app.post("/jira-webhook")
async def jira_webhook_endpoint(request: Request):
    """FastAPI endpoint receiving Jira webhook events."""
    try:
        body = await request.json()
        issue_key = body.get("issue", {}).get("key")
        if not issue_key:
            return {"status": "error", "message": "No issue key found in webhook data"}

        # Find associated group chat
        data_store = telegram_post_data_store.load_data_store()
        group_chat_info = telegram_post_data_store.find_group_chat_by_issue(
            data_store,
            issue_key,
        )
        if not group_chat_info:
            LOGGER.warning(f"No group chat mapping found for issue {issue_key}")
            return {"status": "ignored", "message": "No group chat mapping found"}

        group_chat_id = group_chat_info["group_chat_id"]
        reply_message_id = group_chat_info.get("reply_message_id")

        # Handle comment events
        if body.get("issue_event_type_name") == "issue_commented":
            await handle_comment_event(body, group_chat_id, reply_message_id, issue_key)
            return {"status": "success", "message": "Comment processed"}

        # Handle changelog events
        changelog = body.get("changelog", {}).get("items", [])
        for item in changelog:
            field = item.get("field")
            if field == "status":
                await handle_status_change(
                    item,
                    issue_key,
                    group_chat_id,
                    reply_message_id,
                    group_chat_info,
                )
            elif field in ["duedate", "due date"]:
                await handle_due_date_change(
                    item,
                    issue_key,
                    group_chat_id,
                    reply_message_id,
                )
            elif field == "assignee":
                assignee = item.get("toString")
                assignee = jira_repository.jira.issue(issue_key).fields.assignee.name
                user_cfg = user_config.get_user_config_by_jira_username(assignee)
                telegram_username = user_cfg.telegram_username if user_cfg else None
                
                if assignee and telegram_username:
                    # Send notification to the group
                    message = f"<b>👤Task Assigned</b>\n\nTask has been assigned to @{telegram_username}"
                    send_telegram_message(
                        group_chat_id,
                        message,
                        reply_message_id=reply_message_id,
                        parse_mode="html",
                        token=TELEGRAM_SETTINGS.HOOK_TOKEN
                    )
                    LOGGER.info(f"Sent reassignment notification to group for {issue_key}")
                    
                    # Send direct message to the assigned person
                    if user_cfg.telegram_id:
                        issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
                        issue = jira_repository.jira.issue(issue_key)
                        dm_message = (
                            f"<b>📋 New Task Assigned to You</b>\n\n"
                            f"<b>Task:</b> {issue_key}\n"
                            f"<b>Summary:</b> {issue.fields.summary}\n"
                            f"<b>Link:</b> {issue_link}"
                        )
                        send_telegram_message(
                            user_cfg.telegram_id,
                            dm_message,
                            parse_mode="html",
                            token=TELEGRAM_SETTINGS.HOOK_TOKEN
                        )
                        LOGGER.info(f"Sent direct notification to {telegram_username} for {issue_key}")

        return {"status": "success", "message": "Webhook processed"}

    except Exception as e:
        LOGGER.error(f"Error processing Jira webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def handle_channel_post(channel_post: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming channel posts."""
    username = channel_post.get("from", {}).get("username", "UnknownUser")
    text = channel_post.get("text") or channel_post.get("caption") or ""

    parsed_fields = parse_jira_prompt(text)
    task_data = create_task_data(username, parsed_fields, original_text=text)

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
        await telegram_post_data_store.save_mapping(
            message["message_id"],
            "pending",  # Will be updated when issue is created
            message["chat"]["id"],
            message["chat"]["id"],  # Initially set to channel ID, will be updated on auto-forward
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
    await telegram_post_data_store.save_mapping(
        channel_post_id,
        issue.key,
        chat_id,
        chat_id,
        message_data=channel_post,
    )


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
    issue_key = telegram_post_data_store.get_issue_key_from_channel_post(
        original_message_id,
    )
    group_chat_id = message["chat"]["id"]

    if issue_key:
        # Always update the group_chat_id and reply_message_id in the data store
        data_local = telegram_post_data_store.load_data_store()
        if str(original_message_id) in data_local:
            entry = data_local[str(original_message_id)]
            entry["group_chat_id"] = group_chat_id
            entry["metadata"]["forwarded_at"] = int(time.time())
            entry["reply_message_id"] = message_id
            telegram_post_data_store.save_data_store(data_local)
        
        # Send message only if issue is not pending
        if issue_key != "pending":
            issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
            issue_message = f"Jira Issue Created:\nLink: {issue_link}"
            send_telegram_message(
                group_chat_id,
                issue_message,
                reply_message_id=message_id,
                token=TELEGRAM_SETTINGS.HOOK_TOKEN
            )
            LOGGER.info(
                f"Sent Jira issue link to group chat_id={group_chat_id}: {issue_link}",
            )
        else:
            LOGGER.info(
                f"Auto-forward received for pending issue (message_id={original_message_id}). Group chat updated, awaiting issue creation.",
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
    text = message.get("text") or message.get("caption") or ""

    try:
        issue_key = telegram_post_data_store.find_issue_key_from_message_id(
            f"{message['reply_to_message']['forward_from_message_id']}",
        )
    except KeyError:
        LOGGER.warning(f"Invalid message structure in group chat_id={chat_id}")
        return {
            "status": "ignored",
            "reason": "Invalid message structure",
        }

    if not issue_key:
        LOGGER.warning(f"No Jira issue mapping found for group chat_id={chat_id}")
        return {
            "status": "ignored",
            "reason": "No Jira issue mapping found for this group.",
        }

    user_cfg = user_config.get_user_config(message_from)
    jira_username = user_cfg.jira_username if user_cfg else None
    
    if not jira_username:
        LOGGER.warning(f"No jira_username found for user: {message_from}")
        return {
            "status": "ignored",
            "reason": "User not configured in system",
        }

    # Handle commands
    command_result = await process_command(text, issue_key, message_from, jira_username)
    if command_result:
        return command_result

    # Handle regular comments
    if text:
        formatted_comment = f"h6. Comment from [~{jira_username}] :\n\n{text}"
        jira_repository.add_comment(issue_key, formatted_comment)
        LOGGER.info(f"Added comment to Jira issue {issue_key}")
        return {
            "status": "success",
            "message": "Comment added to Jira issue.",
        }

    return {
        "status": "ignored",
        "reason": "No comment text provided",
    }


def get_user_assignee_and_reporter(username: str) -> tuple[str | None, str | None]:
    """Get assignee and reporter for a given username.
    
    Args:
        username: Telegram username
        
    Returns:
        Tuple of (assignee, reporter). Both are None if user not found in config.
    """
    user_cfg = user_config.get_user_config(username)
    
    if user_cfg:
        return user_cfg.jira_username, user_cfg.jira_username
    else:
        LOGGER.warning(f"User {username} not found in config, using API caller as reporter")
        return None, None


def create_task_data(username: str, parsed_fields: Dict[str, str], original_text: str = "") -> TaskData:
    """Create TaskData object from parsed fields."""
    assignee, reporter = get_user_assignee_and_reporter(username)
    
    # Create description with both original message and parsed description
    parsed_description = parsed_fields.get("description", "")
    
    # Build the combined description with titles
    if original_text and parsed_description:
        description = f'h3. Original Message from User:\n"{original_text}"\n\nh3. AI Analysis:\n{parsed_description}'
    elif original_text:
        description = f'h3. Original Message from User:\n"{original_text}"'
    elif parsed_description:
        description = f'h3. AI Analysis:\n{parsed_description}'
    else:
        description = ""
    
    return TaskData(
        project_key=JIRA_PROJECT_KEY,
        summary=parsed_fields["summary"],
        description=description,
        task_type=parsed_fields["task_type"],
        labels=[parsed_fields.get("labels", "")],
        assignee=assignee,
        reporter=reporter,
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

                # Get assignee and reporter for the user
                assignee, reporter = get_user_assignee_and_reporter(username)
                
                # Create description with both original message and parsed description
                parsed_description = parsed_fields.get("description", "")
                
                # Build the combined description with titles
                if text and parsed_description:
                    description = f'h3. Original Message from User:\n"{text}"\n\nh3. AI Analysis:\n{parsed_description}'
                elif text:
                    description = f'h3. Original Message from User:\n"{text}"'
                elif parsed_description:
                    description = f'h3. AI Analysis:\n{parsed_description}'
                else:
                    description = ""

                task_data = TaskData(
                    project_key=JIRA_PROJECT_KEY,
                    summary=parsed_fields["summary"],
                    description=description,
                    task_type=parsed_fields["task_type"],
                    assignee=assignee,
                    reporter=reporter,
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
