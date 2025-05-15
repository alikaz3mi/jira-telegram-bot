"""Telegram webhook endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import TelegramUpdate, WebhookResponse
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint
from jira_telegram_bot.use_cases.webhooks import TelegramWebhookUseCase


class TelegramWebhookEndpoint(ServiceAPIEndpointBluePrint):
    """API endpoint for handling Telegram webhook events."""
    
    def __init__(self, telegram_webhook_use_case: TelegramWebhookUseCase):
        """Initialize the endpoint.
        
        Args:
            telegram_webhook_use_case: Use case for handling Telegram webhooks
        """
        self.telegram_webhook_use_case = telegram_webhook_use_case
    
    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for Telegram webhooks.
        
        Returns:
            Configured APIRouter for Telegram webhook endpoints
        """
        api_route = APIRouter(
            prefix="/webhook/telegram",
            tags=["Webhooks"]
        )
        
        @api_route.post(
            "/",
            summary="Handle Telegram webhook events",
            description="Receives and processes Telegram webhook events",
            response_model=WebhookResponse
        )
        async def telegram_webhook(request: Request):
            """Handle Telegram webhook events.
            
            Args:
                request: The FastAPI request object
                
            Returns:
                Response with status and message
            """
            try:
                # Parse the JSON payload
                update_data = await request.json()
                LOGGER.debug(f"Received Telegram update: {update_data}")
                
                # Process the update
                result = await self.telegram_webhook_use_case.process_update(update_data)
                return JSONResponse(content=result.dict())
                
            except Exception as e:
                LOGGER.error(f"Error handling Telegram webhook: {str(e)}", exc_info=True)
                return JSONResponse(
                    content=WebhookResponse(
                        status="error",
                        message=f"Error: {str(e)}"
                    ).dict(),
                    status_code=500
                )
        
        return api_route
