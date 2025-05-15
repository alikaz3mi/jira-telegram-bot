"""Jira webhook endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import JiraWebhookRequest, WebhookResponse
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint
from jira_telegram_bot.use_cases.webhooks import JiraWebhookUseCase


class JiraWebhookEndpoint(ServiceAPIEndpointBluePrint):
    """API endpoint for handling Jira webhook events."""
    
    def __init__(self, jira_webhook_use_case: JiraWebhookUseCase):
        """Initialize the endpoint.
        
        Args:
            jira_webhook_use_case: Use case for handling Jira webhooks
        """
        self.jira_webhook_use_case = jira_webhook_use_case
    
    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for Jira webhooks.
        
        Returns:
            Configured APIRouter for Jira webhook endpoints
        """
        api_route = APIRouter(
            prefix="/webhook/jira",
            tags=["Webhooks"]
        )
        
        @api_route.post(
            "/",
            summary="Handle Jira webhook events",
            description="Receives and processes Jira webhook events",
            response_model=WebhookResponse
        )
        async def jira_webhook(request: Request):
            """Handle Jira webhook events.
            
            Args:
                request: The FastAPI request object
                
            Returns:
                Response with status and message
            """
            try:
                # Parse the JSON payload
                webhook_data = await request.json()
                LOGGER.debug(f"Received Jira webhook: {webhook_data}")
                
                # Process the webhook
                result = await self.jira_webhook_use_case.process_webhook(webhook_data)
                return JSONResponse(content=result.dict())
                
            except Exception as e:
                LOGGER.error(f"Error handling Jira webhook: {str(e)}", exc_info=True)
                return JSONResponse(
                    content=WebhookResponse(
                        status="error",
                        message=f"Error: {str(e)}"
                    ).dict(),
                    status_code=500
                )
        
        return api_route
