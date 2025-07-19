"""Generic webhook endpoint that delegates to appropriate controllers."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.controllers.base_webhook_controller import BaseWebhookController
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint


class WebhookEndpoint(ServiceAPIEndpointBluePrint):
    """Generic webhook endpoint that delegates to appropriate controllers."""
    
    def __init__(self, controller: BaseWebhookController, route_prefix: str, route_tags: list[str]):
        """Initialize the webhook endpoint.
        
        Args:
            controller: The webhook controller to handle requests
            route_prefix: URL prefix for the endpoint
            route_tags: OpenAPI tags for the endpoint
        """
        self.controller = controller
        self.route_prefix = route_prefix
        self.route_tags = route_tags
        super().__init__()
    
    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for webhook endpoints.
        
        Returns:
            Configured APIRouter for webhook endpoints
        """
        api_route = APIRouter(
            prefix=self.route_prefix,
            tags=self.route_tags
        )
        
        @api_route.post(
            "/",
            summary="Handle webhook events",
            description="Receives and processes webhook events",
            response_model=WebhookResponse
        )
        async def webhook_handler(request: Request):
            """Handle webhook events.
            
            Args:
                request: The FastAPI request object
                
            Returns:
                Response with status and message
            """
            try:
                # Parse the JSON payload
                webhook_data = await request.json()
                LOGGER.debug(f"Received webhook: {webhook_data}")
                
                # Delegate to controller
                result = await self.controller.process_webhook(webhook_data)
                return JSONResponse(content=result.dict())
                
            except Exception as e:
                LOGGER.error(f"Error handling webhook: {str(e)}", exc_info=True)
                return JSONResponse(
                    content=WebhookResponse(
                        status="error",
                        message=f"Error: {str(e)}"
                    ).dict(),
                    status_code=500
                )
        
        return api_route
