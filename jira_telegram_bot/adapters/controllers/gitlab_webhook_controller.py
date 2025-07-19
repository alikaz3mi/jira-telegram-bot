"""GitLab webhook controller for routing webhook events to appropriate use cases."""

from __future__ import annotations

from typing import Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.controllers.base_webhook_controller import BaseWebhookController
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.use_cases.metrics.process_gitlab_event_use_case import ProcessGitlabEventUseCase


class GitlabWebhookController(BaseWebhookController):
    """Controller for handling GitLab webhook events and routing to appropriate use cases."""
    
    def __init__(self, process_gitlab_event_use_case: ProcessGitlabEventUseCase):
        """Initialize the GitLab webhook controller.
        
        Args:
            process_gitlab_event_use_case: Use case for processing GitLab events into metrics
        """
        super().__init__()
        self.process_gitlab_event_use_case = process_gitlab_event_use_case
    
    def _validate_webhook_data(self, webhook_data: Dict[str, Any]) -> WebhookResponse | None:
        """Validate GitLab webhook data.
        
        Args:
            webhook_data: Raw webhook payload
            
        Returns:
            WebhookResponse if validation fails, None if valid
        """
        object_kind = webhook_data.get("object_kind")
        project_info = webhook_data.get("project", {})
        
        if not object_kind:
            return self._create_ignored_response("No object_kind found in webhook data")
        
        if not project_info:
            return self._create_ignored_response("No project information found in webhook data")
        
        # Validate specific event types
        if object_kind == "push":
            commits = webhook_data.get("commits", [])
            if not commits:
                return self._create_ignored_response("No commits found in push event")
        
        elif object_kind == "merge_request":
            mr_data = webhook_data.get("object_attributes", {})
            if not mr_data:
                return self._create_ignored_response("No merge request data found")
        
        return None
    
    async def _route_to_use_case(self, webhook_data: Dict[str, Any]) -> WebhookResponse:
        """Route GitLab webhook to appropriate use cases.
        
        Args:
            webhook_data: Validated webhook payload
            
        Returns:
            WebhookResponse from use case processing
        """
        object_kind = webhook_data.get("object_kind")
        project_name = webhook_data.get("project", {}).get("name", "unknown")
        
        LOGGER.debug(f"Routing GitLab webhook - Type: {object_kind}, Project: {project_name}")
        
        # Process for metrics
        metrics_success = await self.process_gitlab_event_use_case.process_gitlab_webhook(webhook_data)
        
        if metrics_success:
            return self._create_success_response(
                f"Successfully processed {object_kind} event for project {project_name}"
            )
        else:
            return self._create_error_response(
                f"Failed to process {object_kind} event for project {project_name}"
            )
