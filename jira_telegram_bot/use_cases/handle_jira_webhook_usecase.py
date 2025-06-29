from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_status_constants import JiraStatusConstants
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.utils.data_store import get_mapping_by_issue_key


class HandleJiraWebhookUseCase:
    """
    Use case responsible for handling a Jira webhook event.
    Parses the event, checks local data mappings, and sends
    relevant notifications to Telegram if needed.
    """

    def __init__(self, 
                jira_settings: JiraConnectionSettings,
                 telegram_gateway: NotificationGatewayInterface,
                 jira_repository: TaskManagerRepositoryInterface
                 ):
        self.jira_settings = jira_settings
        self._telegram_gateway = telegram_gateway
        self._jira_repository = jira_repository

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
            f"🔑 Issue Key: {self.jira_settings.domain.scheme}://{self.jira_settings.domain.host}/browse/{issue_data['key']}\n\n"
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
                    # Check permission for review to done transition
                    if not self._check_transition_permission(issue_data, webhook_body, from_str, to_str):
                        user_display_name = webhook_body.get("user", {}).get("displayName", "Unknown")
                        self._revert_status_and_comment(issue_data["key"], from_str, user_display_name)
                        
                        msg = (
                            f"**Jira Event - Action Reverted**\n"
                            f"Issue *{issue_data['key']}* was reverted from '{to_str}' back to '{from_str}'.\n"
                            f"Only the reporter or Jira administrators can move issues from Review to Done."
                        )
                        self._send_notifications(
                            channel_chat_id,
                            group_chat_id,
                            reply_message_id,
                            msg,
                        )
                        return {
                            "status": "reverted",
                            "message": f"Status change reverted for {issue_data['key']} due to insufficient permissions",
                        }
                    
                    # If transitioning to done, update time estimate to zero
                    if to_str.lower() == JiraStatusConstants.DONE.value.lower():
                        self._update_time_estimate_to_zero(issue_data["key"])
                    
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

    def _check_transition_permission(self, issue_data: Dict[str, Any], webhook_body: Dict[str, Any], from_status: str, to_status: str) -> bool:
        """
        Check if the user has permission to transition from review to done.
        Only the reporter or Jira admin can move from review to done.
        """
        if from_status.lower() != JiraStatusConstants.REVIEW.value.lower():
            return True
            
        if to_status.lower() != JiraStatusConstants.DONE.value.lower():
            return True
            
        user = webhook_body.get("user", {})
        user_name = user.get("name", "")
        
        if not user_name:
            return False
            
        issue_reporter = issue_data.get("fields", {}).get("reporter", {}).get("name", "")
        
        # Check if user is the reporter
        if user_name == issue_reporter:
            return True
            
        # Check if user is Jira admin
        return self._jira_repository.is_user_jira_admin(user_name)

    def _revert_status_and_comment(self, issue_key: str, original_status: str, user_display_name: str) -> None:
        """
        Revert the issue status back to the original status and add a comment.
        """
        try:
            # Transition back to original status
            self._jira_repository.transition_task(issue_key, original_status)
            
            # Add comment explaining the reversion
            comment = (
                f"Issue was reverted to '{original_status}' by system. "
                f"Only the reporter or Jira administrators can move issues from Review to Done. "
                f"User {user_display_name} does not have permission for this action."
            )
            self._jira_repository.add_comment(issue_key, comment)
            
            LOGGER.info(f"Reverted issue {issue_key} to {original_status} due to insufficient permissions")
            
        except Exception as e:
            LOGGER.error(f"Error reverting status for issue {issue_key}: {e}")

    def _update_time_estimate_to_zero(self, issue_key: str) -> None:
        """
        Update the remaining time estimate to zero when issue is moved to done.
        """
        try:
            self._jira_repository.update_time_estimate(issue_key, "0h")
            LOGGER.info(f"Updated remaining time estimate to 0h for issue {issue_key}")
        except Exception as e:
            LOGGER.error(f"Error updating time estimate for issue {issue_key}: {e}")

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
