from __future__ import annotations

import json
import os
import time
from typing import Dict, Any, Optional

from jira_telegram_bot.frameworks.fast_api.create_ticket import DATA_STORE_PATH


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


def find_group_chat_by_issue(
    data_store: Dict[str, Any],
    issue_key: str,
) -> Optional[Dict[str, Any]]:
    """Find the group chat info for a given issue key."""
    for entry in data_store.values():
        if entry.get("issue_key") == issue_key:
            return entry
    return None
