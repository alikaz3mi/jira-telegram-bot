from __future__ import annotations

import json
import os
from typing import Any
from typing import Dict
from typing import Optional

from jira_telegram_bot import DEFAULT_PATH

DATA_STORE_PATH = f"{DEFAULT_PATH}/data_store.json"


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


def save_mapping(channel_post_id: int, issue_key: str, chat_id: int, group_id: int):
    """
    Save the mapping between a channel post (message_id) and
    Jira issue, plus the group chat ID if applicable.
    """
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


def get_mapping_by_issue_key(issue_key: str) -> dict | None:
    """
    Look for the dictionary entry whose "issue_key" matches the given issue_key.
    Returns the matching dict if found, else None.
    """
    data_store = load_data_store()
    for _, entry in data_store.items():
        if entry.get("issue_key") == issue_key:
            return entry
    return None


def save_comment(channel_post_id: int, comment: str):
    """
    Save a user's comment into the data store under the specific channel post ID.
    """
    data = load_data_store()
    if str(channel_post_id) not in data:
        data[str(channel_post_id)] = {}
    data[str(channel_post_id)].setdefault("comments", []).append(comment)
    save_data_store(data)
