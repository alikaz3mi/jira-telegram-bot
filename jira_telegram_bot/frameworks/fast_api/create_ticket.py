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
from jira_telegram_bot.utils.mention_parser import (
    convert_jira_mentions_to_telegram,
    get_mentioned_user_configs,
)


JIRA_SETTINGS = JiraConnectionSettings()
TELEGRAM_SETTINGS = TelegramConnectionSettings()
app = FastAPI()
telegram_post_data_store = TelegramPostDataStore()
jira_repository = JiraServerRepository(JIRA_SETTINGS)
user_config = UserConfig()


def lookup_user_config_by_jira_username(jira_username: str):
    """Lookup user configuration by Jira identifier with multiple fallbacks.

    Tries several method names to be compatible with different mocks and implementations
    used in tests and deployments: `get_user_config_by_jira_username`,
    `get_user_by_jira_username`, and `get_user_config_by_jira_username`.
    """
    if not jira_username:
        return None

    # Try the provider names most commonly used in tests/implementations first
    for method_name in (
        "get_user_by_jira_username",
        "get_user_config",
        "get_user_config_by_jira_username",
        "get_user_config_by_jira_name",
    ):
        func = getattr(user_config, method_name, None)
        if callable(func):
            try:
                result = func(jira_username)
                # Basic sanity: expect an object with either jira_username or telegram_id
                if result and (hasattr(result, "jira_username") or hasattr(result, "telegram_id")):
                    return result
                # If the callable returned something unexpected (e.g., a plain MagicMock), skip it
                continue
            except Exception:
                # Continue trying other methods if this one fails
                continue

    # Fallback: attempt to search all configs (if available)
    try:
        all_configs = getattr(user_config, "get_all_user_configs", None)
        if callable(all_configs):
            for cfg in all_configs().values():
                if getattr(cfg, "jira_username", "").lower() == str(jira_username).lower():
                    return cfg
    except Exception:
        pass

    return None


def build_telegram_channel_post_link(channel_chat_id: int, message_id: int) -> str:
    """Build a Telegram channel post link from chat_id and message_id.
    
    Args:
        channel_chat_id: The channel chat ID (with -100 prefix)
        message_id: The message ID
        
    Returns:
        The full Telegram channel post URL
    """
    # Format: https://t.me/c/{channel_id_without_prefix}/{message_id}
    # Remove -100 prefix from channel_chat_id for the link
    channel_id_for_link = str(channel_chat_id).replace("-100", "")
    return f"https://t.me/c/{channel_id_for_link}/{message_id}"


def add_telegram_link_to_description(task_data: TaskData, telegram_post_link: str) -> None:
    """Add Telegram channel post link to task description.
    
    Args:
        task_data: The TaskData object to update
        telegram_post_link: The Telegram post URL to add
    """
    current_description = task_data.description or ""
    task_data.description = f"{current_description}\n\nh3. Telegram Channel Post:\n{telegram_post_link}"


def format_issue_created_message(issue_key: str, telegram_post_link: str) -> str:
    """Format the issue created message with both Jira and Telegram links.
    
    Args:
        issue_key: The Jira issue key
        telegram_post_link: The Telegram post URL
        
    Returns:
        Formatted message string
    """
    issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
    return f"Jira Issue Created:\n\nJira: {issue_link}\nTelegram: {telegram_post_link}"


def extract_channel_info_from_forward(message: Dict[str, Any]) -> tuple[int | None, int | None]:
    """Extract channel chat_id and message_id from a forwarded message.
    
    Supports both old and new Telegram Bot API formats.
    
    Args:
        message: The forwarded message dict
        
    Returns:
        Tuple of (channel_chat_id, channel_message_id) or (None, None) if not found
    """
    # New Bot API 6.9+ format
    if "forward_origin" in message:
        forward_origin = message["forward_origin"]
        channel_chat_id = forward_origin.get("chat", {}).get("id")
        channel_message_id = forward_origin.get("message_id")
        return channel_chat_id, channel_message_id
    
    # Old deprecated format
    if "forward_from_chat" in message and "forward_from_message_id" in message:
        channel_chat_id = message["forward_from_chat"].get("id")
        channel_message_id = message["forward_from_message_id"]
        return channel_chat_id, channel_message_id
    
    return None, None


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
                file_size = vid.get("file_size", 0)
                file_size_mb = file_size / (1024 * 1024) if file_size else 0
                
                # Telegram Bot API getFile has 20MB limit
                if file_size > 20 * 1024 * 1024:
                    LOGGER.warning(
                        f"Video file too large ({file_size_mb:.2f}MB > 20MB limit). "
                        f"Skipping attachment. Consider using direct download or file hosting."
                    )
                    continue
                
                LOGGER.info(f"Processing video: file_id={file_id}, size={file_size_mb:.2f}MB")
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

    # Build Telegram channel post link and add to description
    channel_chat_id = messages[0]["chat"]["id"]
    channel_message_id = messages[0]["message_id"]
    telegram_post_link = build_telegram_channel_post_link(channel_chat_id, channel_message_id)
    add_telegram_link_to_description(task_data, telegram_post_link)
    
    # Create the Jira task
    issue = jira_repository.create_task(task_data)
    
    # Format success message
    issue_message = f"Task created (media group) successfully!\n\nJira: {JIRA_SETTINGS.domain.scheme}://{JIRA_SETTINGS.domain.host}/browse/{issue.key}\nTelegram: {telegram_post_link}"
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
            file_size = vid.get("file_size", 0)
            file_size_mb = file_size / (1024 * 1024) if file_size else 0
            
            # Telegram Bot API getFile has 20MB limit
            if file_size > 20 * 1024 * 1024:
                LOGGER.warning(
                    f"Video file too large ({file_size_mb:.2f}MB > 20MB limit). "
                    f"Ticket will be created without video attachment. "
                    f"File ID: {file_id}"
                )
            else:
                LOGGER.info(f"Processing video: file_id={file_id}, size={file_size_mb:.2f}MB")
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

    # Build Telegram channel post link and add to description
    channel_chat_id = channel_post["chat"]["id"]
    channel_message_id = channel_post["message_id"]
    telegram_post_link = build_telegram_channel_post_link(channel_chat_id, channel_message_id)
    add_telegram_link_to_description(task_data, telegram_post_link)
    
    # Create the Jira task
    issue = jira_repository.create_task(task_data)
    
    # Format success message
    issue_message = f"Task created (single) successfully!\n\nJira: {JIRA_SETTINGS.domain}/browse/{issue.key}\nTelegram: {telegram_post_link}"
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
    """Handle a new comment event from Jira webhook.
    
    Sends notification to group chat, DMs the assignee if comment is from someone else,
    and notifies all mentioned users.
    """
    comment = body.get("comment", {})
    if not comment:
        return  

    comment_body = comment.get("body", "")
    jira_username = comment.get("author", {}).get("name", "UnknownUser")
    user_cfg_for_comment = lookup_user_config_by_jira_username(jira_username)
    telegram_username = user_cfg_for_comment.telegram_username if user_cfg_for_comment else None

    # Skip if this is a comment we posted from Telegram (comments from Telegram start with this marker)
    if comment_body.strip().startswith("h6. Comment from"):
        LOGGER.debug(f"Skipping Telegram-originated comment on {issue_key}")
        return

    # Convert Jira mentions to Telegram mentions
    converted_comment, mentioned_telegram_users = convert_jira_mentions_to_telegram(comment_body, user_config)
    
    # Send notification to group chat with converted mentions
    commenter_display = f"@{telegram_username}" if telegram_username else jira_username
    comment_content = f"Comment from {commenter_display}:\n\n{converted_comment}"
    # Use plain text (no parse_mode) to avoid entity parsing errors with Persian/Unicode text and @mentions
    message = (
        f"💬 Comment Added\n\nTask {issue_key} has a new comment:\n\n{comment_content}"
    )
    
    try:
        send_telegram_message(
            group_chat_id,
            message,
            reply_message_id=reply_message_id,
            parse_mode=None,
            token=TELEGRAM_SETTINGS.HOOK_TOKEN
        )
        LOGGER.info(f"Sent comment notification to group {group_chat_id} for {issue_key}")
    except Exception as e:
        LOGGER.error(f"Failed to send comment notification to group {group_chat_id} for {issue_key}: {e}")
    
    # Get mentioned users from the comment
    mentioned_user_configs = get_mentioned_user_configs(comment_body, user_config)
    
    # Send DM to assignee if comment is from someone else
    try:
        issue = jira_repository.jira.issue(issue_key)
        assignee = issue.fields.assignee
        assignee_jira_username = assignee.name if assignee and hasattr(assignee, "name") else None
        
        # Send DM to assignee (if not the commenter)
        if assignee_jira_username and assignee_jira_username != jira_username:
            assignee_cfg = lookup_user_config_by_jira_username(assignee_jira_username)
            
            if assignee_cfg and getattr(assignee_cfg, "telegram_user_chat_id", None):
                commenter_mention = f"@{telegram_username}" if telegram_username else jira_username
                issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
                
                dm_message = (
                    f"<b>💬 New comment from {commenter_mention} on {issue_key}:</b>\n\n"
                    f"{converted_comment}\n\n"
                    f"<b>Link:</b> {issue_link}"
                )
                
                try:
                    send_telegram_message(
                        assignee_cfg.telegram_user_chat_id,
                        dm_message,
                        parse_mode="html",
                        token=TELEGRAM_SETTINGS.TOKEN,
                    )
                    LOGGER.info(f"Sent comment DM to assignee {assignee_jira_username} for {issue_key}")
                except Exception as dm_error:
                    LOGGER.warning(f"Failed to send DM to assignee {assignee_jira_username} (chat_id={assignee_cfg.telegram_user_chat_id}): {dm_error}. User may not have started bot.")
        
        # Send DM to all mentioned users (excluding commenter and assignee who already got notified)
        for mentioned_cfg in mentioned_user_configs:
            mentioned_jira_username = getattr(mentioned_cfg, "jira_username", None)
            mentioned_telegram_chat_id = getattr(mentioned_cfg, "telegram_user_chat_id", None)
            
            # Skip if this is the commenter or assignee (already notified)
            if mentioned_jira_username == jira_username:
                continue
            if mentioned_jira_username == assignee_jira_username:
                continue
                
            if mentioned_telegram_chat_id:
                commenter_mention = f"@{telegram_username}" if telegram_username else jira_username
                issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
                mentioned_telegram_username = getattr(mentioned_cfg, "telegram_username", mentioned_jira_username)
                
                dm_message = (
                    f"<b>👋 You were mentioned by {commenter_mention} in {issue_key}:</b>\n\n"
                    f"{converted_comment}\n\n"
                    f"<b>Link:</b> {issue_link}"
                )
                
                try:
                    send_telegram_message(
                        mentioned_telegram_chat_id,
                        dm_message,
                        parse_mode="html",
                        token=TELEGRAM_SETTINGS.TOKEN,
                    )
                    LOGGER.info(f"Sent mention notification to @{mentioned_telegram_username} for {issue_key}")
                except Exception as dm_error:
                    LOGGER.warning(f"Failed to send mention DM to @{mentioned_telegram_username} (chat_id={mentioned_telegram_chat_id}): {dm_error}. User may not have started bot.")
                
    except Exception as e:
        LOGGER.warning(f"Could not send notification DMs for {issue_key}: {e}")


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
    """Convert a Gregorian date string to Jalali format.
    
    Supports multiple formats:
    - ISO format: YYYY-MM-DD HH:MM
    - Jira format: 16/Nov/25 8:17 AM
    """
    try:
        from datetime import datetime
        
        # Try parsing different date formats
        parsed_date = None
        
        # Try ISO format first (YYYY-MM-DD)
        if "-" in date_str:
            if " " not in date_str:
                date_str += " 00:00"
            year, month, day = date_str.split(" ")[0].split("-")
            time = date_str.split(" ")[1]
            parsed_date = datetime(int(year), int(month), int(day))
        # Try Jira format (16/Nov/25 8:17 AM)
        elif "/" in date_str:
            # Parse formats like "16/Nov/25 8:17 AM"
            try:
                parsed_date = datetime.strptime(date_str, "%d/%b/%y %I:%M %p")
            except ValueError:
                # Try without time
                parsed_date = datetime.strptime(date_str.split(" ")[0], "%d/%b/%y")
            time = parsed_date.strftime("%H:%M")
        
        if parsed_date:
            georgian_time = jdatetime.GregorianToJalali(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
            )
            return f"{georgian_time.jyear}/{georgian_time.jmonth}/{georgian_time.jday} {time}"
        else:
            return date_str
            
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
        # Allow the original creator, PCT admins, or a superadmin to mark as done
        allowed_to_mark_done = False

        # Creator of the post can always mark as done
        if store_entry and store_entry.get("metadata", {}).get("creator_username") == message_from:
            allowed_to_mark_done = True

        # Try to resolve user config and check roles (PCT admin or superadmin)
        if not allowed_to_mark_done:
            try:
                user_cfg = user_config.get_user_config(message_from)
                # Check board_roles if present
                board_roles = getattr(user_cfg, "board_roles", None) if user_cfg else None
                if isinstance(board_roles, dict):
                    # PCT admin explicitly allowed
                    if board_roles.get("PCT") == "admin":
                        allowed_to_mark_done = True
                    # Global superadmin role allowed (if any board has role 'superadmin')
                    if any(role == "superadmin" for role in board_roles.values()):
                        allowed_to_mark_done = True
            except Exception:
                # If user_config lookup fails, fall back to denying permission
                allowed_to_mark_done = allowed_to_mark_done

        if allowed_to_mark_done:
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

        # If the returned object isn't a plain dict (some test mocks return MagicMock
        # objects which are truthy), treat it as not found and try the channel-post lookup.
        if not isinstance(group_chat_info, dict):
            group_chat_info = telegram_post_data_store.find_channel_post_by_issue(
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
            field_lower = field.lower() if field else ""
            if field == "status":
                await handle_status_change(
                    item,
                    issue_key,
                    group_chat_id,
                    reply_message_id,
                    group_chat_info,
                )
            elif field_lower in ["duedate", "due date"]:
                await handle_due_date_change(
                    item,
                    issue_key,
                    group_chat_id,
                    reply_message_id,
                )
            elif field == "assignee":
                # Attempt to determine the new assignee from the changelog item and issue payload.
                assignee_from_item = item.get("toString")
                assignee_obj = body.get("issue", {}).get("fields", {}).get("assignee") or {}

                # Collect candidate identifiers (order: changelog toString, assignee.name, assignee.accountId, assignee.displayName)
                candidates: list = []
                if assignee_from_item:
                    candidates.append(str(assignee_from_item))
                if isinstance(assignee_obj, dict):
                    if assignee_obj.get("name"):
                        candidates.append(str(assignee_obj.get("name")))
                    if assignee_obj.get("accountId"):
                        candidates.append(str(assignee_obj.get("accountId")))
                    if assignee_obj.get("displayName"):
                        candidates.append(str(assignee_obj.get("displayName")))
                else:
                    # Fallback to reading from Jira API if available
                    try:
                        jira_assignee = jira_repository.jira.issue(issue_key).fields.assignee
                        if jira_assignee:
                            if hasattr(jira_assignee, "name") and jira_assignee.name:
                                candidates.append(str(jira_assignee.name))
                            if hasattr(jira_assignee, "accountId") and jira_assignee.accountId:
                                candidates.append(str(jira_assignee.accountId))
                            if hasattr(jira_assignee, "displayName") and jira_assignee.displayName:
                                candidates.append(str(jira_assignee.displayName))
                    except Exception:
                        # If Jira API is not reachable or assignee not available, continue with candidates we have
                        LOGGER.debug(f"Could not fetch issue {issue_key} from Jira to resolve assignee")

                # Try to find a user config for any candidate identifier
                user_cfg = None
                matched_identifier = None
                for candidate in candidates:
                    if not candidate:
                        continue
                    user_cfg = lookup_user_config_by_jira_username(candidate)
                    if user_cfg:
                        matched_identifier = candidate
                        break

                # Always send a group-level notification so the team knows assignment changed
                assigned_display = assignee_from_item or (
                    assignee_obj.get("displayName") if isinstance(assignee_obj, dict) else None
                ) or matched_identifier or "<unknown>"
                
                # Add Telegram mention if we found a user config with telegram_username
                telegram_mention = ""
                if user_cfg and getattr(user_cfg, "telegram_username", None):
                    telegram_mention = f" @{user_cfg.telegram_username}"
                
                group_message = f"<b>👤 Task Assigned</b>\n\nTask has been assigned to {assigned_display}{telegram_mention}"
                send_telegram_message(
                    group_chat_id,
                    group_message,
                    reply_message_id=reply_message_id,
                    parse_mode="html",
                    token=TELEGRAM_SETTINGS.HOOK_TOKEN,
                )
                LOGGER.info(f"Sent reassignment notification to group for {issue_key}: {assigned_display}{telegram_mention}")

                # If we found a user config with a telegram_id, DM the assignee directly
                if user_cfg and getattr(user_cfg, "telegram_user_chat_id", None):
                    issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
                    try:
                        issue = jira_repository.jira.issue(issue_key)
                        summary = issue.fields.summary
                    except Exception:
                        summary = None

                    dm_message = (
                        f"<b>📋 New Task Assigned to You from ParsChat Support Team</b>\n\n"
                        f"<b>Task:</b> {issue_key}\n"
                        + (f"<b>Summary:</b> {summary}\n" if summary else "")
                        + f"<b>Link:</b> {issue_link}"
                    )
                    send_telegram_message(
                        user_cfg.telegram_user_chat_id,
                        dm_message,
                        parse_mode="html",
                        token=TELEGRAM_SETTINGS.TOKEN,
                    )
                    LOGGER.info(f"Sent direct notification to {getattr(user_cfg, 'telegram_username', matched_identifier)} for {issue_key}")

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
    # Support both old (forward_from_chat) and new (is_automatic_forward) Telegram API formats
    is_auto_forward = (
        message.get("is_automatic_forward", False) is True
        or "forward_from_chat" in message
    )
    
    if is_auto_forward:
        return await handle_auto_forward_message(message)
    else:
        return await handle_group_comment(message)


async def handle_auto_forward_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle automatically forwarded messages from channel to group.
    
    Supports both old and new Telegram Bot API formats:
    - Old format (deprecated): forward_from_chat, forward_from_message_id
    - New format (Bot API 6.9+): is_automatic_forward, forward_origin
    """
    message_id = message["message_id"]
    
    # Support both old and new Telegram API formats
    if "forward_origin" in message:
        # New Bot API 6.9+ format
        forward_origin = message["forward_origin"]
        original_message_id = forward_origin.get("message_id")
    else:
        # Old deprecated format (but still widely used)
        original_message_id = message.get("forward_from_message_id")
    
    if not original_message_id:
        LOGGER.warning("Could not extract original message ID from forwarded message")
        return {"status": "error", "message": "Invalid forward message structure"}
    
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
            # Extract channel info from the forwarded message
            channel_chat_id, channel_message_id = extract_channel_info_from_forward(reply_to_message)
            
            # Build message with both Jira and Telegram links if available
            if channel_chat_id and channel_message_id:
                telegram_post_link = build_telegram_channel_post_link(channel_chat_id, channel_message_id)
                issue_message = format_issue_created_message(issue_key, telegram_post_link)
            else:
                # Fallback to Jira link only
                issue_link = f"{JIRA_SETTINGS.domain}browse/{issue_key}"
                issue_message = f"Jira Issue Created:\nLink: {issue_link}"
            
            send_telegram_message(
                group_chat_id,
                issue_message,
                reply_message_id=message_id,
                token=TELEGRAM_SETTINGS.HOOK_TOKEN
            )
            LOGGER.info(
                f"Sent Jira issue link to group chat_id={group_chat_id}: {issue_key}",
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

async def handle_edited_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle edited messages in group chats.
    
    Updates the corresponding Jira comment when a Telegram message is edited.
    Uses stored telegram_message_id -> jira_comment_id mapping for exact updates.
    Note: Currently only supports editing text, not media attachments.
    """
    chat_id = message["chat"]["id"]
    message_id = message["message_id"]
    
    # Check if this is an anonymous admin message
    is_anonymous = (
        message.get("from", {}).get("username") == "GroupAnonymousBot"
        or "sender_chat" in message
    )
    
    if is_anonymous:
        message_from = None
        LOGGER.info(f"Processing edited anonymous admin message in chat_id={chat_id}")
    else:
        message_from = message.get("from", {}).get("username", "UnknownUser")
    
    text = message.get("text") or message.get("caption") or ""
    
    if not text:
        LOGGER.warning(f"Edited message {message_id} has no text, skipping")
        return {"status": "ignored", "reason": "No text in edited message"}
    
    # Look up the stored comment mapping
    comment_mapping = telegram_post_data_store.find_comment_mapping(message_id, chat_id)
    
    if not comment_mapping:
        LOGGER.warning(f"No comment mapping found for message {message_id} in chat {chat_id}")
        return {"status": "ignored", "reason": "No stored comment mapping found"}
    
    jira_comment_id = comment_mapping.get("jira_comment_id")
    issue_key = comment_mapping.get("issue_key")
    
    if not jira_comment_id or not issue_key:
        LOGGER.error(f"Invalid comment mapping data: {comment_mapping}")
        return {"status": "error", "reason": "Invalid comment mapping data"}
    
    # Get user config and format the updated comment
    jira_username = None
    if message_from:
        user_cfg = user_config.get_user_config(message_from)
        jira_username = user_cfg.jira_username if user_cfg else None
    
    if not jira_username:
        if is_anonymous:
            jira_username = "anonymous_admin"
            formatted_comment = f"h6. Comment from Anonymous Admin (edited):\n\n{text}"
        else:
            LOGGER.warning(f"No jira_username found for user: {message_from}")
            return {"status": "ignored", "reason": "User not configured"}
    else:
        formatted_comment = f"h6. Comment from [~{jira_username}] (edited):\n\n{text}"
    
    # Update the specific comment in Jira
    try:
        issue = jira_repository.jira.issue(issue_key)
        comment = jira_repository.jira.comment(issue_key, jira_comment_id)
        
        if comment:
            comment.update(body=formatted_comment)
            LOGGER.info(f"Updated comment {jira_comment_id} on {issue_key} for edited message {message_id}")
            return {"status": "success", "message": "Comment updated in Jira"}
        else:
            LOGGER.warning(f"Comment {jira_comment_id} not found on {issue_key}")
            return {"status": "error", "reason": "Comment not found in Jira"}
            
    except Exception as e:
        LOGGER.error(f"Failed to update comment {jira_comment_id} for edited message {message_id}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def handle_group_comment(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle comments in group chats.
    
    Supports both regular user messages and anonymous admin (GroupAnonymousBot) messages.
    For anonymous messages, extracts the real user from the message context.
    """
    chat_id = message["chat"]["id"]
    
    # Check if this is an anonymous admin message (GroupAnonymousBot or sender_chat)
    is_anonymous = (
        message.get("from", {}).get("username") == "GroupAnonymousBot"
        or "sender_chat" in message
    )
    
    # For anonymous messages, we need to infer the user differently
    if is_anonymous:
        # The actual user info might be in the thread context,   not in 'from'
        # We'll try to get it from the message content or skip user attribution
        message_from = None
        LOGGER.info(f"Processing anonymous admin message in chat_id={chat_id}")
    else:
        message_from = message.get("from", {}).get("username", "UnknownUser")
    
    text = message.get("text") or message.get("caption") or ""

    # Find the issue key from the replied-to message
    reply_to_message = message.get("reply_to_message")
    if not reply_to_message:
        LOGGER.warning(f"Group message has no reply_to_message in chat_id={chat_id}")
        return {
            "status": "ignored",
            "reason": "No reply context",
        }
    
    # Try multiple ways to find the issue key
    issue_key = None
    original_message_id = None
    
    # Method 1: New Bot API format (forward_origin) - for auto-forwarded channel posts
    if "forward_origin" in reply_to_message:
        forward_origin = reply_to_message["forward_origin"]
        original_message_id = forward_origin.get("message_id")
        if original_message_id:
            issue_key = telegram_post_data_store.find_issue_key_from_message_id(str(original_message_id))
    
    # Method 2: Old format (forward_from_message_id) - for auto-forwarded channel posts
    if not issue_key and "forward_from_message_id" in reply_to_message:
        original_message_id = reply_to_message["forward_from_message_id"]
        issue_key = telegram_post_data_store.find_issue_key_from_message_id(str(original_message_id))
    
    # Method 3: Direct reply to a group message (not forwarded from channel)
    # This handles replies within the group thread
    if not issue_key:
        replied_message_id = reply_to_message.get("message_id")
        if replied_message_id:
            # Look up the issue from the group message being replied to
            data_store = telegram_post_data_store.load_data_store()
            for entry in data_store.values():
                if entry.get("reply_message_id") == replied_message_id:
                    issue_key = entry.get("issue_key")
                    if issue_key and issue_key != "pending":
                        LOGGER.info(f"Found issue {issue_key} from group reply_message_id={replied_message_id}")
                        break
    
    # Method 4: Use message_thread_id to find the issue
    # For Telegram topics/threads, all messages in a thread share the same message_thread_id
    if not issue_key:
        thread_id = message.get("message_thread_id")
        if thread_id:
            data_store = telegram_post_data_store.load_data_store()
            for entry in data_store.values():
                # Check if the reply_message_id in our data matches the thread_id
                if entry.get("reply_message_id") == thread_id:
                    issue_key = entry.get("issue_key")
                    if issue_key and issue_key != "pending":
                        LOGGER.info(f"Found issue {issue_key} from message_thread_id={thread_id}")
                        break

    if not issue_key:
        LOGGER.warning(f"No Jira issue mapping found for original_message_id={original_message_id}")
        return {
            "status": "ignored",
            "reason": "No Jira issue mapping found for this group.",
        }

    # Get user config and Jira username
    jira_username = None
    if message_from:
        user_cfg = user_config.get_user_config(message_from)
        jira_username = user_cfg.jira_username if user_cfg else None
    
    if not jira_username:
        if is_anonymous:
            # For anonymous messages, use a generic attribution
            LOGGER.info(f"Anonymous comment on {issue_key}, using generic attribution")
            jira_username = "anonymous_admin"
        else:
            LOGGER.warning(f"No jira_username found for user: {message_from}")
            return {
                "status": "ignored",
                "reason": "User not configured in system",
            }
    
    # Handle commands for both identified users and anonymous admins
    command_result = await process_command(text, issue_key, message_from, jira_username)
    if command_result:
        return command_result
    
    # Format the comment based on user type
    if is_anonymous:
        formatted_comment = f"h6. Comment from Anonymous Admin:\n\n{text}"
    else:
        formatted_comment = f"h6. Comment from [~{jira_username}] :\n\n{text}"

    # Collect media attachments from the message
    media_files = []
    media_descriptions = []  # Track media types and names for comment
    has_media = False
    
    async with aiohttp.ClientSession() as session:
        # Handle photo(s)
        if "photo" in message:
            has_media = True
            photo_array = message["photo"]
            file_id = photo_array[-1]["file_id"]  # Get largest photo
            mock_media = MockTelegramPhoto(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            media_path = f"comment_photo_{message['message_id']}.jpg"
            try:
                await fetch_and_store_media(mock_media, session, media_files, media_path, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                media_descriptions.append(f"📷 Image: [^{media_path}]")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch photo for comment: {e}")
        
        # Handle document
        if "document" in message:
            has_media = True
            doc = message["document"]
            file_id = doc["file_id"]
            file_name = doc.get("file_name", f"comment_doc_{message['message_id']}")
            mock_media = MockTelegramDocument(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            try:
                await fetch_and_store_media(mock_media, session, media_files, file_name, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                media_descriptions.append(f"📄 Document: [^{file_name}]")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch document for comment: {e}")
        
        # Handle video
        if "video" in message:
            has_media = True
            vid = message["video"]
            file_id = vid["file_id"]
            file_size = vid.get("file_size", 0)
            file_size_mb = file_size / (1024 * 1024) if file_size else 0
            
            if file_size > 20 * 1024 * 1024:
                LOGGER.warning(f"Video too large ({file_size_mb:.2f}MB) for comment on {issue_key}")
                media_descriptions.append(f"🎥 Video: _(file too large, not attached - {file_size_mb:.2f}MB)_")
            else:
                mock_media = MockTelegramVideo(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                media_path = f"comment_video_{message['message_id']}.mp4"
                try:
                    await fetch_and_store_media(mock_media, session, media_files, media_path, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                    media_descriptions.append(f"🎥 Video: [^{media_path}]")
                except Exception as e:
                    LOGGER.warning(f"Failed to fetch video for comment: {e}")
        
        # Handle audio/voice
        if "audio" in message or "voice" in message:
            has_media = True
            audio_data = message.get("audio") or message.get("voice")
            file_id = audio_data["file_id"]
            mock_media = MockTelegramAudio(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
            media_path = f"comment_audio_{message['message_id']}.mp3"
            media_type = "🎵 Audio" if "audio" in message else "🎤 Voice"
            try:
                await fetch_and_store_media(mock_media, session, media_files, media_path, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
                media_descriptions.append(f"{media_type}: [^{media_path}]")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch audio/voice for comment: {e}")
    
    # Append media descriptions to the comment
    if media_descriptions:
        formatted_comment += "\n\n*Attachments:*\n" + "\n".join(media_descriptions)

    # Add comment to Jira
    if text or has_media:
        comment = jira_repository.add_comment(issue_key, formatted_comment)
        
        # Store the mapping of telegram_message_id -> jira_comment_id for edit support
        if comment and hasattr(comment, 'id'):
            telegram_message_id = message.get("message_id")
            chat_id = message["chat"]["id"]
            telegram_post_data_store.store_comment_mapping(
                telegram_message_id=telegram_message_id,
                chat_id=chat_id,
                jira_comment_id=comment.id,
                issue_key=issue_key
            )
            LOGGER.info(f"Stored comment mapping: telegram_msg={telegram_message_id} -> jira_comment={comment.id}")
        
        # Attach media files if any
        if media_files:
            try:
                jira_repository.handle_attachments(issue_key, {"images": media_files})
                LOGGER.info(f"Added comment with {len(media_files)} attachment(s) to {issue_key}")
            except Exception as e:
                LOGGER.warning(f"Failed to attach media to comment on {issue_key}: {e}")
        else:
            LOGGER.info(f"Added text comment to Jira issue {issue_key}")
        
        return {
            "status": "success",
            "message": "Comment added to Jira issue.",
        }

    return {
        "status": "ignored",
        "reason": "No comment text or media provided",
    }


def get_user_assignee_and_reporter(username: str) -> tuple[str | None, str | None]:
    """Get assignee and reporter for a given username.
    
    Args:
        username: Telegram username
        
    Returns:
        Tuple of (assignee, reporter). 
        - assignee is always None (tasks are unassigned by default, PM assigns later)
        - reporter is the user's Jira username if found in config, None otherwise
    """
    user_cfg = user_config.get_user_config(username)
    
    if user_cfg:
        # Return None for assignee (unassigned), user's jira_username for reporter
        return None, user_cfg.jira_username
    else:
        LOGGER.warning(f"User {username} not found in config, ticket will be unassigned with no reporter")
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
    elif "edited_channel_post" in data:
        LOGGER.info(
            f"Handling edited channel post with ID: {data['edited_channel_post'].get('message_id')}",
        )
        # For now, treat edited channel posts as new posts
        # TODO: Implement issue update logic if needed
        return {"status": "ignored", "reason": "Channel post edits not yet supported"}
    elif "edited_message" in data:
        LOGGER.info(
            f"Handling edited message with ID: {data['edited_message'].get('message_id')}",
        )
        return await handle_edited_message(data["edited_message"])
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
