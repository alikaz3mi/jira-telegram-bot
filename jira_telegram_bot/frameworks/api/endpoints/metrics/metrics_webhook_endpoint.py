"""FastAPI webhook endpoint for metrics processing."""

from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint
from jira_telegram_bot.use_cases.metrics.process_jira_event_use_case import ProcessJiraEventUseCase
from jira_telegram_bot.use_cases.metrics.process_gitlab_event_use_case import ProcessGitlabEventUseCase


class JiraWebhookPayload(BaseModel):
    """Pydantic model for Jira webhook payload."""
    
    issue_event_type_name: str = None
    issue: Dict[str, Any] = {}
    changelog: Dict[str, Any] = None
    worklog: Dict[str, Any] = None
    timestamp: str = None


class GitLabWebhookPayload(BaseModel):
    """Pydantic model for GitLab webhook payload."""
    
    object_kind: str
    event_type: str = None
    project: Dict[str, Any] = {}
    commits: list[Dict[str, Any]] = []
    object_attributes: Dict[str, Any] = {}


class MetricsWebhookEndpoint(ServiceAPIEndpointBluePrint):
    """FastAPI endpoint for processing webhooks and updating metrics."""
    
    def __init__(
        self,
        process_jira_event_use_case: ProcessJiraEventUseCase,
        process_gitlab_event_use_case: ProcessGitlabEventUseCase
    ):
        """Initialize the endpoint.
        
        Args:
            process_jira_event_use_case: Use case for processing Jira events
            process_gitlab_event_use_case: Use case for processing GitLab events
        """
        super().__init__()
        self.process_jira_event_use_case = process_jira_event_use_case
        self.process_gitlab_event_use_case = process_gitlab_event_use_case
    
    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for metrics webhook endpoints.
        
        Returns:
            APIRouter with metrics webhook routes configured
        """
        api_route = APIRouter()
        
        @api_route.post("/jira", tags=["Metrics"])
        async def process_jira_webhook(
            payload: Dict[str, Any],
            background_tasks: BackgroundTasks
        ) -> WebhookResponse:
            """Process Jira webhook for metrics tracking.
            
            Args:
                payload: Raw webhook payload from Jira
                background_tasks: FastAPI background tasks
                
            Returns:
                WebhookResponse indicating success or failure
            """
            try:
                LOGGER.info(f"Received Jira webhook for metrics processing")
                LOGGER.debug(f"Jira webhook payload: {payload}")
                
                # Process in background to avoid blocking webhook response
                background_tasks.add_task(
                    self._process_jira_webhook_background,
                    payload
                )
                
                return WebhookResponse(
                    status="success",
                    message="Jira webhook received and queued for metrics processing"
                )
                
            except Exception as e:
                LOGGER.error(f"Error processing Jira webhook: {e}")
                return WebhookResponse(
                    status="error",
                    message=f"Failed to process Jira webhook: {str(e)}"
                )
        
        @api_route.post("/gitlab", tags=["Metrics"])
        async def process_gitlab_webhook(
            payload: Dict[str, Any],
            background_tasks: BackgroundTasks
        ) -> WebhookResponse:
            """Process GitLab webhook for metrics tracking.
            
            Args:
                payload: Raw webhook payload from GitLab
                background_tasks: FastAPI background tasks
                
            Returns:
                WebhookResponse indicating success or failure
            """
            try:
                LOGGER.info(f"Received GitLab webhook for metrics processing")
                LOGGER.debug(f"GitLab webhook payload: {payload}")
                
                # Process in background to avoid blocking webhook response
                background_tasks.add_task(
                    self._process_gitlab_webhook_background,
                    payload
                )
                
                return WebhookResponse(
                    status="success",
                    message="GitLab webhook received and queued for metrics processing"
                )
                
            except Exception as e:
                LOGGER.error(f"Error processing GitLab webhook: {e}")
                return WebhookResponse(
                    status="error",
                    message=f"Failed to process GitLab webhook: {str(e)}"
                )
        
        @api_route.get("/health", tags=["Metrics"])
        async def health_check() -> Dict[str, str]:
            """Health check endpoint for metrics processing.
            
            Returns:
                Status dictionary
            """
            return {
                "status": "healthy",
                "service": "metrics-webhook-processor"
            }
        
        return api_route
    
    async def _process_jira_webhook_background(self, payload: Dict[str, Any]) -> None:
        """Process Jira webhook in background task.
        
        Args:
            payload: Raw webhook payload from Jira
        """
        try:
            success = await self.process_jira_event_use_case.process_jira_webhook(payload)
            if success:
                LOGGER.info("Successfully processed Jira webhook for metrics")
            else:
                LOGGER.error("Failed to process Jira webhook for metrics")
                
        except Exception as e:
            LOGGER.error(f"Error in background Jira webhook processing: {e}")
    
    async def _process_gitlab_webhook_background(self, payload: Dict[str, Any]) -> None:
        """Process GitLab webhook in background task.
        
        Args:
            payload: Raw webhook payload from GitLab
        """
        try:
            success = await self.process_gitlab_event_use_case.process_gitlab_webhook(payload)
            if success:
                LOGGER.info("Successfully processed GitLab webhook for metrics")
            else:
                LOGGER.error("Failed to process GitLab webhook for metrics")
                
        except Exception as e:
            LOGGER.error(f"Error in background GitLab webhook processing: {e}")
