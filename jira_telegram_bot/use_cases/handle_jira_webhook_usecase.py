from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.interface.telegram_gateway_interface import (
    TelegramGatewayInterface,
)
from jira_telegram_bot.utils.data_store import get_mapping_by_issue_key


class HandleJiraWebhookUseCase:
    """
    Use case responsible for handling a Jira webhook event.
    Parses the event, checks local data mappings, and sends
    relevant notifications to Telegram if needed.
    """

    def __init__(self, telegram_gateway: TelegramGatewayInterface):
        self._telegram_gateway = telegram_gateway

    def run(self, webhook_body: Dict[str, Any]) -> Dict[str, str]:
        """
        Processes the JSON body from a Jira webhook.
        Returns a status dict with 'status' and 'message'.
        """
        LOGGER.debug(f"Jira Webhook data: {webhook_body}")
        event_type = webhook_body.get("issue_event_type_name")
        issue_data = webhook_body.get("issue", {})
        issue_key = issue_data.get("key")

        if not issue_key or not event_type:
            return {"status": "ignored", "reason": "No issue_key or event_type found."}

        # Look up the local mapping
        mapping = get_mapping_by_issue_key(issue_key)
        if not mapping:
            LOGGER.debug(f"No local Telegram mapping found for issue_key={issue_key}.")
            return {
                "status": "ignored",
                "reason": "No matching issue_key in local data.",
            }

        channel_chat_id = mapping.get("channel_chat_id")
        group_chat_id = mapping.get("group_chat_id")
        reply_message_id = mapping.get("reply_message_id")

        # Distinguish events
        if event_type == "issue_created":
            return self._handle_issue_created(
                issue_data,
                webhook_body,
                channel_chat_id,
                group_chat_id,
                reply_message_id,
            )

        elif event_type == "issue_generic":
            return self._handle_issue_generic(
                issue_data,
                webhook_body,
                channel_chat_id,
                group_chat_id,
                reply_message_id,
            )

        elif event_type == "issue_updated":
            return self._handle_issue_updated(
                issue_data,
                webhook_body,
                channel_chat_id,
                group_chat_id,
                reply_message_id,
            )

        # Unhandled event
        return {"status": "ignored", "message": f"Unhandled event_type: {event_type}"}

    def _handle_issue_created(
        self,
        issue_data,
        webhook_body,
        channel_chat_id,
        group_chat_id,
        reply_message_id,
    ):
        summary = issue_data["fields"].get("summary", "")
        creator_name = webhook_body.get("user", {}).get("displayName", "someone")
        msg = (
            f"**Jira Event**\n"
            f"Issue *created* by {creator_name}\n"
            f"Key: {issue_data['key']}\n"
            f"Summary: {summary}"
        )
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        return {
            "status": "success",
            "message": f"Issue created => posted for {issue_data['key']}",
        }

    def _handle_issue_generic(
        self,
        issue_data,
        webhook_body,
        channel_chat_id,
        group_chat_id,
        reply_message_id,
    ):
        summary = issue_data["fields"].get("summary", "")
        creator_name = webhook_body.get("user", {}).get("displayName", "someone")
        msg = (
            f"🔔 *Jira Event*\n\n"
            f"🔑 Issue Key: {JIRA_SETTINGS.domain}/browse/{issue_data['key']}\n\n"
            f"📝 Summary: {summary}\n\n"
            f"👤 Created by {creator_name}"
        )
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        return {
            "status": "success",
            "message": f"Issue created => posted for {issue_data['key']}",
        }

    def _handle_issue_updated(
        self,
        issue_data,
        webhook_body,
        channel_chat_id,
        group_chat_id,
        reply_message_id,
    ):
        comment_info = webhook_body.get("comment")
        if comment_info:
            commenter = comment_info["updateAuthor"]["displayName"]
            comment_body = comment_info["body"]
            msg = (
                f"**Jira Event**\n"
                f"New comment on *{issue_data['key']}* by {commenter}:\n\n"
                f"{comment_body}"
            )
            self._send_notifications(
                channel_chat_id,
                group_chat_id,
                reply_message_id,
                msg,
            )
            return {
                "status": "success",
                "message": f"Comment => posted for {issue_data['key']}",
            }

        # Check for status changes
        changelog = webhook_body.get("changelog", {})
        items = changelog.get("items", [])
        for change_item in items:
            if change_item.get("field") == "status":
                from_str = change_item.get("fromString", "")
                to_str = change_item.get("toString", "")
                if from_str and to_str:
                    msg = (
                        f"**Jira Event**\n"
                        f"Issue *{issue_data['key']}* moved from '{from_str}' to '{to_str}'."
                    )
                    self._send_notifications(
                        channel_chat_id,
                        group_chat_id,
                        reply_message_id,
                        msg,
                    )
                    return {
                        "status": "success",
                        "message": f"Status changed => posted for {issue_data['key']}",
                    }

        return {"status": "ignored", "message": "Issue updated, no relevant event."}

    def _send_notifications(
        self,
        channel_chat_id,
        group_chat_id,
        reply_message_id,
        message_text,
    ):
        """
        Send the given message_text to the channel/group if they exist.
        """
        if channel_chat_id:
            self._telegram_gateway.send_message(
                channel_chat_id,
                message_text,
                reply_message_id,
            )
        if group_chat_id and group_chat_id != channel_chat_id:
            self._telegram_gateway.send_message(group_chat_id, message_text)
