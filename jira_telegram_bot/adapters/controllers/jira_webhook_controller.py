"""Jira webhook controller for routing webhook events to appropriate use cases."""

from __future__ import annotations

from typing import Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.controllers.base_webhook_controller import BaseWebhookController
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.use_cases.webhooks import JiraWebhookUseCase
from jira_telegram_bot.use_cases.metrics.process_jira_event_use_case import ProcessJiraEventUseCase
from jira_telegram_bot.use_cases.team_evaluation import SprintWebhookHandler


class JiraWebhookController(BaseWebhookController):
    """Controller for handling Jira webhook events and routing to appropriate use cases."""
    
    def __init__(
        self,
        jira_webhook_use_case: JiraWebhookUseCase,
        process_jira_event_use_case: ProcessJiraEventUseCase,
        sprint_webhook_handler: SprintWebhookHandler = None
    ):
        """Initialize the Jira webhook controller.
        
        Args:
            jira_webhook_use_case: Use case for handling Jira webhooks
            process_jira_event_use_case: Use case for processing Jira events into metrics
            sprint_webhook_handler: Handler for sprint-related events (optional)
        """
        super().__init__()
        self.jira_webhook_use_case = jira_webhook_use_case
        self.process_jira_event_use_case = process_jira_event_use_case
        self.sprint_webhook_handler = sprint_webhook_handler
    
    def _validate_webhook_data(self, webhook_data: Dict[str, Any]) -> WebhookResponse | None:
        """Validate Jira webhook data.
        
        Args:
            webhook_data: Raw webhook payload
            
        Returns:
            WebhookResponse if validation fails, None if valid
        """
        basic_info = self._extract_basic_info(webhook_data)
        event_type = basic_info.get("event_type")
        issue_key = basic_info.get("issue_key")
        
        if not event_type:
            return self._create_ignored_response("No event_type found in webhook data")
        
        # if not issue_key:
        #     return self._create_ignored_response("No issue_key found in webhook data")
        
        return None
    
    async def _route_to_use_case(self, webhook_data: Dict[str, Any]) -> WebhookResponse:
        """Route Jira webhook to appropriate use cases.
        
        Args:
            webhook_data: Validated webhook payload
            
        Returns:
            WebhookResponse from use case processing
        """
        basic_info = self._extract_basic_info(webhook_data)
        event_type = basic_info.get("event_type")
        issue_key = basic_info.get("issue_key")
        
        LOGGER.debug(f"Routing Jira webhook - Event: {event_type}, Issue: {issue_key}")
        
        results = []
        
        # Always process for notifications (if mapping exists)
        notification_result = await self.jira_webhook_use_case.process_webhook(webhook_data)
        results.append(f"Notification: {notification_result.message}")
        
        # Always process for metrics
        metrics_success = await self.process_jira_event_use_case.process_jira_webhook(webhook_data)
        if metrics_success:
            results.append("Metrics: Successfully processed")
        else:
            results.append("Metrics: Processing failed")
        
        # Process sprint events if handler is available
        if self.sprint_webhook_handler and self._is_sprint_event(webhook_data):
            try:
                await self.sprint_webhook_handler.handle_sprint_event(webhook_data)
                results.append("Sprint: Successfully processed team evaluation")
            except Exception as e:
                LOGGER.error(f"Sprint webhook processing failed: {e}")
                results.append(f"Sprint: Processing failed - {e}")
        
        # Combine results
        combined_message = f"Processed {event_type} for {issue_key}. " + " | ".join(results)
        
        # Return success if at least one processing succeeded
        if notification_result.status == "success" or metrics_success:
            return self._create_success_response(combined_message)
        elif notification_result.status == "ignored":
            return self._create_ignored_response(combined_message)
        else:
            return self._create_error_response(combined_message)

    def _is_sprint_event(self, webhook_data: Dict[str, Any]) -> bool:
        """Check if the webhook is a sprint-related event.
        
        Args:
            webhook_data: Webhook payload
            
        Returns:
            True if this is a sprint event
        """
        event_type = webhook_data.get("webhookEvent", "")
        return event_type in ["sprint_closed", "sprint_started", "sprint_updated"]
