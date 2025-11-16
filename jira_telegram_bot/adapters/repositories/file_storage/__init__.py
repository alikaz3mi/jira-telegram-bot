from __future__ import annotations

import json
import os
import time
from typing import Any
from typing import Dict
from typing import Optional

from jira_telegram_bot import DEFAULT_PATH

DATA_STORE_PATH = f"{DEFAULT_PATH}/data_store.json"


class TelegramPostDataStore:
    def __init__(self, data_store_path: str = DATA_STORE_PATH):
        self.data_store_path = data_store_path

    def load_data_store(self) -> Dict[str, Any]:
        """Load the data store from the JSON file."""
        if not os.path.exists(self.data_store_path):
            return {}
        with open(self.data_store_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_data_store(self, data: Dict[str, Any]):
        """Save the data store to the JSON file."""
        with open(self.data_store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def save_mapping(
        self,
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
        data = self.load_data_store()

        # Extract additional metadata
        created_at = message_data.get(
            "date",
            int(time.time()),
        )  # Fallback to current time
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
        self.save_data_store(data)

    def get_issue_key_from_channel_post(self, channel_post_id: int) -> Optional[str]:
        """Retrieve the Jira issue key associated with a channel post."""
        data = self.load_data_store()
        return data.get(str(channel_post_id), {}).get("issue_key")

    def get_group_chat_id_from_channel_post(
        self,
        channel_post_id: int,
    ) -> Optional[int]:
        """Retrieve the group chat ID associated with a channel post."""
        data = self.load_data_store()
        return data.get(str(channel_post_id), {}).get("group_chat_id")

    def find_issue_key_for_group(self, chat_id: int) -> Optional[str]:
        """Find the Jira issue key associated with a group chat."""
        data_store = self.load_data_store()
        for mapping in data_store.values():
            if mapping.get("group_chat_id") == chat_id:
                return mapping.get("issue_key")
        return None

    def find_issue_key_from_message_id(self, message_id: int) -> Optional[str]:
        """Find the Jira issue key associated with a message ID."""
        data_store = self.load_data_store()
        return data_store.get(str(message_id), {}).get("issue_key")

    def find_group_chat_by_issue(
        self,
        data_store: Dict[str, Any],
        issue_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Find the group chat info for a given issue key.
        
        Prioritizes entries with reply_message_id and where group_chat_id differs
        from channel_chat_id (indicating the message was forwarded to a group).
        This ensures webhook notifications reply to the correct thread.
        """
        candidates = []
        for entry in data_store.values():
            if entry.get("issue_key") == issue_key:
                candidates.append(entry)
        
        if not candidates:
            return None
        
        # Prioritize entries with reply_message_id and different group_chat_id
        for entry in candidates:
            has_reply_id = "reply_message_id" in entry
            group_id = entry.get("group_chat_id")
            channel_id = entry.get("channel_chat_id")
            is_forwarded = group_id and channel_id and group_id != channel_id
            
            if has_reply_id and is_forwarded:
                return entry
        
        # Fallback to any entry with reply_message_id
        for entry in candidates:
            if "reply_message_id" in entry:
                return entry
        
        # Last resort: return first match
        return candidates[0]

    def find_channel_post_by_issue(
        self,
        data_store: Dict[str, Any],
        issue_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Find the channel post info for a given issue key."""
        for entry in data_store.values():
            if entry.get("issue_key") == issue_key:
                return entry
        return None

    def store_comment_mapping(
        self,
        telegram_message_id: int,
        chat_id: int,
        jira_comment_id: str,
        issue_key: str,
    ):
        """Store mapping between Telegram message ID and Jira comment ID.
        
        This mapping enables editing Telegram messages to update corresponding Jira comments.
        
        Args:
            telegram_message_id: The Telegram message ID
            chat_id: The chat ID where the message was sent
            jira_comment_id: The Jira comment ID (from API response)
            issue_key: The Jira issue key
        """
        data = self.load_data_store()
        
        # Use a composite key: chat_id_message_id_comment
        comment_key = f"{chat_id}_{telegram_message_id}_comment"
        
        data[comment_key] = {
            "telegram_message_id": telegram_message_id,
            "chat_id": chat_id,
            "jira_comment_id": jira_comment_id,
            "issue_key": issue_key,
            "created_at": int(time.time()),
            "type": "comment_mapping"
        }
        
        self.save_data_store(data)

    def find_comment_mapping(
        self,
        telegram_message_id: int,
        chat_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Find the Jira comment ID for a given Telegram message.
        
        Args:
            telegram_message_id: The Telegram message ID
            chat_id: The chat ID
            
        Returns:
            Dict containing jira_comment_id and issue_key, or None if not found
        """
        data = self.load_data_store()
        comment_key = f"{chat_id}_{telegram_message_id}_comment"
        return data.get(comment_key)
