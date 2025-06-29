from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_issue_status_manager import JiraIssueStatusManager
from jira_telegram_bot.use_cases.webhooks.jira_transition_permission_validator import (
    JiraTransitionPermissionValidator,
)
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)


class JiraIssueUpdatedEventHandler:
    """
    Handles Jira issue updated events including status changes and comments.
    
    Processes complex business logic for status transitions with permission validation.
    """
    
    def __init__(
        self,
        telegram_gateway: NotificationGatewayInterface,
        status_manager: JiraIssueStatusManager,
        permission_validator: JiraTransitionPermissionValidator,
        message_formatter: JiraWebhookMessageFormatter,
    ):
        self._telegram_gateway = telegram_gateway
        self._status_manager = status_manager
        self._permission_validator = permission_validator
        self._message_formatter = message_formatter
    
    def handle(
        self,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Handle issue updated events.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            channel_chat_id: Telegram channel chat ID
            group_chat_id: Telegram group chat ID
            reply_message_id: Reply message ID
            
        Returns:
            Result dictionary with status and message
        """
        # Handle comment events first
        comment_result = self._handle_comment_event(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        if comment_result:
            return comment_result
        
        # Handle status change events
        return self._handle_status_change_event(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
    
    def _handle_comment_event(
        self,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str] | None:
        """
        Handle comment-related events.
        
        Returns:
            Result dictionary if comment was handled, None otherwise
        """
        comment_info = webhook_body.get("comment")
        if not comment_info:
            return None
        
        msg = self._message_formatter.format_comment_message(issue_data, comment_info)
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        
        return {
            "status": "success",
            "message": f"Comment => posted for {issue_data['key']}",
        }
    
    def _handle_status_change_event(
        self,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Handle status change events with permission validation.
        
        Returns:
            Result dictionary with status and message
        """
        changelog = webhook_body.get("changelog", {})
        items = changelog.get("items", [])
        
        for change_item in items:
            if change_item.get("field") == "status":
                from_str = change_item.get("fromString", "")
                to_str = change_item.get("toString", "")
                
                if from_str and to_str:
                    return self._process_status_transition(
                        issue_data, webhook_body, from_str, to_str,
                        channel_chat_id, group_chat_id, reply_message_id
                    )
        
        return {"status": "ignored", "message": "Issue updated, no relevant event."}
    
    def _process_status_transition(
        self,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        from_status: str,
        to_status: str,
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Process a status transition with permission validation and side effects.
        
        Returns:
            Result dictionary with status and message
        """
        issue_key = issue_data["key"]
        
        # Check permission for the transition
        if not self._permission_validator.check_transition_permission(
            issue_data, webhook_body, from_status, to_status
        ):
            return self._handle_unauthorized_transition(
                issue_key, webhook_body, from_status, to_status,
                channel_chat_id, group_chat_id, reply_message_id
            )
        
        # Handle authorized transition
        return self._handle_authorized_transition(
            issue_key, from_status, to_status,
            channel_chat_id, group_chat_id, reply_message_id
        )
    
    def _handle_unauthorized_transition(
        self,
        issue_key: str,
        webhook_body: Dict[str, Any],
        from_status: str,
        to_status: str,
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Handle unauthorized status transitions by reverting and notifying.
        
        Returns:
            Result dictionary for reverted transition
        """
        user_display_name = webhook_body.get("user", {}).get("displayName", "Unknown")
        self._status_manager.revert_status_and_comment(issue_key, from_status, user_display_name)
        
        msg = self._message_formatter.format_status_reversion_message(
            issue_key, to_status, from_status
        )
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        
        return {
            "status": "reverted",
            "message": f"Status change reverted for {issue_key} due to insufficient permissions",
        }
    
    def _handle_authorized_transition(
        self,
        issue_key: str,
        from_status: str,
        to_status: str,
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Handle authorized status transitions with side effects.
        
        Returns:
            Result dictionary for successful transition
        """
        # Update time estimate if transitioning to done
        if self._status_manager.should_update_time_estimate(to_status):
            self._status_manager.update_time_estimate_to_zero(issue_key)
        
        msg = self._message_formatter.format_status_change_message(issue_key, from_status, to_status)
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        
        return {
            "status": "success",
            "message": f"Status changed => posted for {issue_key}",
        }
    
    def _send_notifications(
        self,
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
        message_text: str,
    ) -> None:
        """
        Send notifications to the appropriate Telegram channels.
        
        Args:
            channel_chat_id: Telegram channel chat ID
            group_chat_id: Telegram group chat ID
            reply_message_id: Reply message ID
            message_text: Message to send
        """
        if channel_chat_id:
            self._telegram_gateway.send_message(
                channel_chat_id,
                message_text,
                reply_message_id,
            )
        if group_chat_id and group_chat_id != channel_chat_id:
            self._telegram_gateway.send_message(group_chat_id, message_text)
