from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_issue_status_manager import JiraIssueStatusManager
from jira_telegram_bot.use_cases.webhooks.jira_issue_updated_event_handler import (
    JiraIssueUpdatedEventHandler,
)
from jira_telegram_bot.use_cases.webhooks.jira_simple_event_handler import JiraSimpleEventHandler
from jira_telegram_bot.use_cases.webhooks.jira_transition_permission_validator import (
    JiraTransitionPermissionValidator,
)
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)
from jira_telegram_bot.utils.data_store import get_mapping_by_issue_key


class HandleJiraWebhookUseCase:
    """
    Main orchestrator for handling Jira webhook events.
    
    Coordinates between different event handlers based on webhook event type.
    Uses composition to delegate specific functionality to specialized handlers.
    """
    
    def __init__(
        self,
        jira_settings: JiraConnectionSettings,
        telegram_gateway: NotificationGatewayInterface,
        jira_repository: TaskManagerRepositoryInterface,
    ):
        self.jira_settings = jira_settings
        self._telegram_gateway = telegram_gateway
        self._jira_repository = jira_repository
        
        # Initialize specialized components
        self._message_formatter = JiraWebhookMessageFormatter(jira_settings)
        self._status_manager = JiraIssueStatusManager(jira_repository)
        self._permission_validator = JiraTransitionPermissionValidator(jira_repository)
        
        # Initialize event handlers
        self._simple_event_handler = JiraSimpleEventHandler(
            telegram_gateway, self._message_formatter
        )
        self._issue_updated_handler = JiraIssueUpdatedEventHandler(
            telegram_gateway,
            self._status_manager,
            self._permission_validator,
            self._message_formatter,
        )
    
    def run(self, webhook_body: Dict[str, Any]) -> Dict[str, str]:
        """
        Process a Jira webhook event.
        
        Args:
            webhook_body: JSON body from Jira webhook
            
        Returns:
            Status dictionary with 'status' and 'message'
        """
        LOGGER.debug(f"Jira Webhook data: {webhook_body}")
        
        # Extract basic webhook information
        validation_result = self._validate_webhook_data(webhook_body)
        if validation_result:
            return validation_result
        
        event_type = webhook_body["issue_event_type_name"]
        issue_data = webhook_body["issue"]
        issue_key = issue_data["key"]
        
        # Get Telegram mapping for the issue
        mapping = get_mapping_by_issue_key(issue_key)
        if not mapping:
            LOGGER.debug(f"No local Telegram mapping found for issue_key={issue_key}.")
            return {
                "status": "ignored",
                "reason": "No matching issue_key in local data.",
            }
        
        # Extract notification targets
        notification_params = self._extract_notification_parameters(mapping)
        
        # Route to appropriate handler based on event type
        return self._route_event(event_type, issue_data, webhook_body, notification_params)
    
    def _validate_webhook_data(self, webhook_body: Dict[str, Any]) -> Dict[str, str] | None:
        """
        Validate that webhook contains required data.
        
        Args:
            webhook_body: JSON body from Jira webhook
            
        Returns:
            Error result if validation fails, None if valid
        """
        event_type = webhook_body.get("issue_event_type_name")
        issue_data = webhook_body.get("issue", {})
        issue_key = issue_data.get("key")
        
        if not issue_key or not event_type:
            return {"status": "ignored", "reason": "No issue_key or event_type found."}
        
        return None
    
    def _extract_notification_parameters(self, mapping: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract notification parameters from mapping data.
        
        Args:
            mapping: Mapping data from data store
            
        Returns:
            Dictionary containing notification parameters
        """
        return {
            "channel_chat_id": mapping.get("channel_chat_id"),
            "group_chat_id": mapping.get("group_chat_id"),
            "reply_message_id": mapping.get("reply_message_id"),
        }
    
    def _route_event(
        self,
        event_type: str,
        issue_data: Dict[str, Any],
        webhook_body: Dict[str, Any],
        notification_params: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Route webhook event to appropriate handler.
        
        Args:
            event_type: Type of Jira event
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            notification_params: Notification parameters (chat IDs, etc.)
            
        Returns:
            Result dictionary from the appropriate handler
        """
        if event_type == "issue_created":
            return self._simple_event_handler.handle_issue_created(
                issue_data, webhook_body, **notification_params
            )
        
        elif event_type == "issue_generic":
            return self._simple_event_handler.handle_issue_generic(
                issue_data, webhook_body, **notification_params
            )
        
        elif event_type == "issue_updated":
            return self._issue_updated_handler.handle(
                issue_data, webhook_body, **notification_params
            )
        
        # Unhandled event type
        return {
            "status": "ignored", 
            "message": f"Unhandled event_type: {event_type}"
        }
