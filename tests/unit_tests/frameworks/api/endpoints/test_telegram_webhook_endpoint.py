"""Unit tests for TelegramWebhookEndpoint."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.endpoints.telegram_webhook import TelegramWebhookEndpoint
from jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case import TelegramWebhookUseCase


class TestTelegramWebhookEndpoint(unittest.TestCase):
    """Test suite for TelegramWebhookEndpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.telegram_webhook_use_case = AsyncMock(spec=TelegramWebhookUseCase)
        self.endpoint = TelegramWebhookEndpoint(
            telegram_webhook_use_case=self.telegram_webhook_use_case
        )
        
        # Create a FastAPI app for testing the endpoint
        self.app = FastAPI()
        self.app.include_router(self.endpoint.create_rest_api_route())
        self.client = TestClient(self.app)
        
    def test_create_rest_api_route(self):
        """Test creating the REST API route."""
        # Arrange
        
        # Act
        router = self.endpoint.create_rest_api_route()
        
        # Assert
        self.assertIsNotNone(router)
        self.assertEqual(router.prefix, "/webhook/telegram")
        self.assertEqual(router.tags, ["Webhooks"])
    
    def test_telegram_webhook_endpoint_success(self):
        """Test successful webhook processing."""
        # Arrange
        update_data = {
            "update_id": 123456789,
            "message": {
                "message_id": 42,
                "chat": {"id": 123456789, "type": "private"},
                "text": "Test message",
                "from": {"id": 123456789, "username": "testuser"}
            }
        }
        
        self.telegram_webhook_use_case.process_update.return_value = WebhookResponse(
            status="success",
            message="Processed update"
        )
        
        # Act
        with patch('fastapi.Request.json', AsyncMock(return_value=update_data)):
            response = self.client.post("/webhook/telegram/", json=update_data)
        
        # Assert
        self.telegram_webhook_use_case.process_update.assert_called_once_with(update_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), 
            {"status": "success", "message": "Processed update"}
        )
    
    def test_telegram_webhook_endpoint_ignored(self):
        """Test ignored update in webhook processing."""
        # Arrange
        update_data = {
            "update_id": 123456789,
            # No message, should be ignored
        }
        
        self.telegram_webhook_use_case.process_update.return_value = WebhookResponse(
            status="ignored",
            message="Unsupported update type"
        )
        
        # Act
        with patch('fastapi.Request.json', AsyncMock(return_value=update_data)):
            response = self.client.post("/webhook/telegram/", json=update_data)
        
        # Assert
        self.telegram_webhook_use_case.process_update.assert_called_once_with(update_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), 
            {"status": "ignored", "message": "Unsupported update type"}
        )
    
    def test_telegram_webhook_endpoint_exception(self):
        """Test exception handling in webhook processing."""
        # Arrange
        update_data = {
            "update_id": 123456789,
            "message": {
                "message_id": 42,
                "chat": {"id": 123456789, "type": "private"},
                "text": "Test message",
                "from": {"id": 123456789, "username": "testuser"}
            }
        }
        
        self.telegram_webhook_use_case.process_update.side_effect = Exception("Test exception")
        
        # Act
        with patch('fastapi.Request.json', AsyncMock(return_value=update_data)):
            response = self.client.post("/webhook/telegram/", json=update_data)
        
        # Assert
        self.telegram_webhook_use_case.process_update.assert_called_once_with(update_data)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(), 
            {"status": "error", "message": "Error: Test exception"}
        )
