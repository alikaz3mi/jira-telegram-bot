"""Use case for handling Jira webhook events."""

from __future__ import annotations

from typing import Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.interfaces.jira_webhook_handler_interface import JiraWebhookHandlerInterface
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import NotificationGatewayInterface
from jira_telegram_bot.utils.data_store import get_mapping_by_issue_key


class JiraWebhookUseCase(JiraWebhookHandlerInterface):
    """Use case for processing Jira webhook events.
    
    This use case handles Jira webhook events, extracts relevant information,
    and sends appropriate notifications via Telegram.
    """
    
    def __init__(
        self, 
        jira_settings: JiraConnectionSettings,
        telegram_gateway: NotificationGatewayInterface
    ):
        """Initialize the use case.
        
        Args:
            jira_settings: Jira connection settings
            telegram_gateway: Gateway for sending Telegram notifications
        """
        self.jira_settings = jira_settings
        self.telegram_gateway = telegram_gateway
    
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> WebhookResponse:
        """Process a Jira webhook event.
        
        Args:
            webhook_data: The webhook payload from Jira
            
        Returns:
            Response with status and message
        """
        LOGGER.debug(f"Jira Webhook data: {webhook_data}")
        
        # Extract event information
        event_type = webhook_data.get("issue_event_type_name")
        issue_data = webhook_data.get("issue", {})
        issue_key = issue_data.get("key")
        
        if not issue_key or not event_type:
            return WebhookResponse(
                status="ignored", 
                message="No issue_key or event_type found"
            )
        
        # Find the associated Telegram mapping
        mapping = get_mapping_by_issue_key(issue_key)
        if not mapping:
            LOGGER.debug(f"No local Telegram mapping found for issue_key={issue_key}.")
            return WebhookResponse(
                status="ignored",
                message="No matching issue_key in local data"
            )
        
        # Process by event type
        try:
            if event_type == "issue_commented":
                await self._handle_comment_event(webhook_data, mapping, issue_key)
            elif event_type == "issue_updated":
                await self._handle_issue_update(webhook_data, mapping, issue_key)
            
            return WebhookResponse(
                status="success",
                message=f"Processed {event_type} event for {issue_key}"
            )
        except Exception as e:
            LOGGER.error(f"Error processing webhook: {str(e)}", exc_info=True)
            return WebhookResponse(
                status="error",
                message=f"Error processing webhook: {str(e)}"
            )
    
    async def _handle_comment_event(
        self, 
        webhook_data: Dict[str, Any],
        mapping: Dict[str, Any],
        issue_key: str
    ) -> None:
        """Handle a comment event from Jira.
        
        Args:
            webhook_data: The webhook payload
            mapping: Telegram channel mapping data
            issue_key: The Jira issue key
        """
        comment_data = webhook_data.get("comment", {})
        comment_body = comment_data.get("body", "")
        comment_author = comment_data.get("author", {}).get("displayName", "Unknown")
        
        # Format message for Telegram
        message = f"💬 <b>New comment on {issue_key}</b>\n\n"
        message += f"<b>{comment_author}</b>: {comment_body}"
        
        # Send to Telegram channel
        channel_chat_id = mapping.get("channel_chat_id")
        reply_to = mapping.get("message_id")
        
        if channel_chat_id:
            await self.telegram_gateway.send_message(
                chat_id=channel_chat_id,
                text=message,
                reply_to_message_id=reply_to,
                parse_mode="HTML"
            )
    
    async def _handle_issue_update(
        self, 
        webhook_data: Dict[str, Any],
        mapping: Dict[str, Any],
        issue_key: str
    ) -> None:
        """Handle an issue update event from Jira.
        
        Args:
            webhook_data: The webhook payload
            mapping: Telegram channel mapping data
            issue_key: The Jira issue key
        """
        changelog = webhook_data.get("changelog", {}).get("items", [])
        channel_chat_id = mapping.get("channel_chat_id")
        reply_to = mapping.get("message_id")
        
        if not channel_chat_id or not changelog:
            return
            
        for change in changelog:
            field = change.get("field")
            old_value = change.get("fromString", "")
            new_value = change.get("toString", "")
            
            if field == "status":
                message = f"🔄 <b>Status Change</b>\n\n"
                message += f"{issue_key}: {old_value} → {new_value}"
                
                await self.telegram_gateway.send_message(
                    chat_id=channel_chat_id,
                    text=message,
                    reply_to_message_id=reply_to,
                    parse_mode="HTML"
                )
            
            elif field == "assignee":
                message = f"👤 <b>Assignment Change</b>\n\n"
                message += f"{issue_key} assigned to: {new_value or 'Unassigned'}"
                
                await self.telegram_gateway.send_message(
                    chat_id=channel_chat_id, 
                    text=message,
                    reply_to_message_id=reply_to,
                    parse_mode="HTML"
                )
