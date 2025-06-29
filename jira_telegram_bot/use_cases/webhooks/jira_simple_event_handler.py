from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)


class JiraSimpleEventHandler:
    """
    Handles simple Jira events that don't require complex business logic.
    
    Manages issue creation and generic events with straightforward message formatting.
    """
    
    def __init__(
        self,
        telegram_gateway: NotificationGatewayInterface,
        message_formatter: JiraWebhookMessageFormatter,
    ):
        self._telegram_gateway = telegram_gateway
        self._message_formatter = message_formatter
    
    def handle_issue_created(
        self,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Handle issue creation events.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            channel_chat_id: Telegram channel chat ID
            group_chat_id: Telegram group chat ID
            reply_message_id: Reply message ID
            
        Returns:
            Result dictionary with status and message
        """
        msg = self._message_formatter.format_issue_created_message(issue_data, webhook_body)
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        
        return {
            "status": "success",
            "message": f"Issue created => posted for {issue_data['key']}",
        }
    
    def handle_issue_generic(
        self,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        channel_chat_id: str,
        group_chat_id: str,
        reply_message_id: str,
    ) -> Dict[str, str]:
        """
        Handle generic issue events.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            channel_chat_id: Telegram channel chat ID
            group_chat_id: Telegram group chat ID
            reply_message_id: Reply message ID
            
        Returns:
            Result dictionary with status and message
        """
        msg = self._message_formatter.format_issue_generic_message(issue_data, webhook_body)
        self._send_notifications(channel_chat_id, group_chat_id, reply_message_id, msg)
        
        return {
            "status": "success",
            "message": f"Issue created => posted for {issue_data['key']}",
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
