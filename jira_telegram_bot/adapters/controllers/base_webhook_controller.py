"""Base webhook controller for handling common webhook operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import WebhookResponse


class BaseWebhookController(ABC):
    """Base controller for webhook processing with common functionality."""
    
    def __init__(self):
        """Initialize the base webhook controller."""
        pass
    
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> WebhookResponse:
        """Process webhook data with common error handling and logging.
        
        Args:
            webhook_data: Raw webhook payload
            
        Returns:
            WebhookResponse with status and message
        """
        try:
            LOGGER.debug(f"Processing webhook: {webhook_data}")
            
            # Validate webhook data
            validation_result = self._validate_webhook_data(webhook_data)
            if validation_result:
                return validation_result
            
            # Route to appropriate use case
            return await self._route_to_use_case(webhook_data)
            
        except Exception as e:
            LOGGER.error(f"Error processing webhook: {str(e)}", exc_info=True)
            return WebhookResponse(
                status="error",
                message=f"Error processing webhook: {str(e)}"
            )
    
    @abstractmethod
    def _validate_webhook_data(self, webhook_data: Dict[str, Any]) -> WebhookResponse | None:
        """Validate webhook data.
        
        Args:
            webhook_data: Raw webhook payload
            
        Returns:
            WebhookResponse if validation fails, None if valid
        """
        pass
    
    @abstractmethod
    async def _route_to_use_case(self, webhook_data: Dict[str, Any]) -> WebhookResponse:
        """Route webhook to appropriate use case.
        
        Args:
            webhook_data: Validated webhook payload
            
        Returns:
            WebhookResponse from use case processing
        """
        pass
    
    def _extract_basic_info(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic information from webhook data.
        
        Args:
            webhook_data: Raw webhook payload
            
        Returns:
            Dictionary with extracted basic information
        """
        # TODO: get webhook data from jira-server repostory or jira cloud repository and not in here
        return {
            "event_type": webhook_data.get("webhookEvent"),
            "issue_key": webhook_data.get("issue", {}).get("key"),
            "timestamp": webhook_data.get("timestamp"),
            "webhook_id": webhook_data.get("webhookEvent")
        }
    
    def _create_success_response(self, message: str) -> WebhookResponse:
        """Create a standardized success response.
        
        Args:
            message: Success message
            
        Returns:
            WebhookResponse with success status
        """
        return WebhookResponse(status="success", message=message)
    
    def _create_ignored_response(self, message: str) -> WebhookResponse:
        """Create a standardized ignored response.
        
        Args:
            message: Ignored message
            
        Returns:
            WebhookResponse with ignored status
        """
        return WebhookResponse(status="ignored", message=message)
    
    def _create_error_response(self, message: str) -> WebhookResponse:
        """Create a standardized error response.
        
        Args:
            message: Error message
            
        Returns:
            WebhookResponse with error status
        """
        return WebhookResponse(status="error", message=message)
