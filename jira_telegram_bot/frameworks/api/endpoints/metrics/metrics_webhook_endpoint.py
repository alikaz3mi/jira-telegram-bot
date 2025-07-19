"""FastAPI webhook endpoint for metrics processing."""

from fastapi import APIRouter, BackgroundTasks
from typing import Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.controllers.jira_webhook_controller import JiraWebhookController
from jira_telegram_bot.adapters.controllers.gitlab_webhook_controller import GitlabWebhookController
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint


class MetricsWebhookEndpoint(ServiceAPIEndpointBluePrint):
    """FastAPI endpoint for processing webhooks and updating metrics."""
    
    def __init__(
        self,
        jira_webhook_controller: JiraWebhookController,
        gitlab_webhook_controller: GitlabWebhookController
    ):
        """Initialize the endpoint.
        
        Args:
            jira_webhook_controller: Controller for handling Jira webhooks
            gitlab_webhook_controller: Controller for handling GitLab webhooks
        """
        super().__init__()
        self.jira_webhook_controller = jira_webhook_controller
        self.gitlab_webhook_controller = gitlab_webhook_controller
    
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
            result = await self.jira_webhook_controller.process_webhook(payload)
            if result.status == "success":
                LOGGER.info("Successfully processed Jira webhook for metrics")
            else:
                LOGGER.error(f"Failed to process Jira webhook for metrics: {result.message}")
                
        except Exception as e:
            LOGGER.error(f"Error in background Jira webhook processing: {e}")
    
    async def _process_gitlab_webhook_background(self, payload: Dict[str, Any]) -> None:
        """Process GitLab webhook in background task.
        
        Args:
            payload: Raw webhook payload from GitLab
        """
        try:
            result = await self.gitlab_webhook_controller.process_webhook(payload)
            if result.status == "success":
                LOGGER.info("Successfully processed GitLab webhook for metrics")
            else:
                LOGGER.error(f"Failed to process GitLab webhook for metrics: {result.message}")
                
        except Exception as e:
            LOGGER.error(f"Error in background GitLab webhook processing: {e}")
