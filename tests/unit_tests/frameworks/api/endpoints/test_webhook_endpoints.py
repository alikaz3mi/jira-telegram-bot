"""Unit tests for webhook endpoints."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request
from fastapi.responses import JSONResponse

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.endpoints.jira_webhook import JiraWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints.telegram_webhook import TelegramWebhookEndpoint


class TestJiraWebhookEndpoint(unittest.TestCase):
    """Test suite for JiraWebhookEndpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.jira_webhook_use_case = AsyncMock()
        self.endpoint = JiraWebhookEndpoint(
            jira_webhook_use_case=self.jira_webhook_use_case
        )
        
        # Set up a success response
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="success",
            message="Webhook processed successfully"
        )
    
    def test_create_rest_api_route(self):
        """Test creating the API router."""
        # Act
        router = self.endpoint.create_rest_api_route()
        
        # Assert
        self.assertEqual(router.prefix, "/webhook/jira")
        self.assertEqual(router.tags, ["Webhooks"])
        self.assertTrue(hasattr(router, "routes"))
        self.assertEqual(len(router.routes), 1)  # Should have one POST route
    
    async def test_a_jira_webhook_success(self):
        """Test successful webhook processing."""
        # Arrange
        mock_request = AsyncMock(spec=Request)
        mock_request.json.return_value = {"issue": {"key": "TEST-123"}}
        
        # Get the route handler
        router = self.endpoint.create_rest_api_route()
        handler = router.routes[0].endpoint
        
        # Act
        response = await handler(mock_request)
        
        # Assert
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 200)
        content = response.body.decode()
        self.assertIn("success", content)
        self.assertIn("Webhook processed successfully", content)
        self.jira_webhook_use_case.process_webhook.assert_called_once_with(
            {"issue": {"key": "TEST-123"}}
        )
    
    async def test_a_jira_webhook_request_error(self):
        """Test error handling when request parsing fails."""
        # Arrange
        mock_request = AsyncMock(spec=Request)
        mock_request.json.side_effect = Exception("Invalid JSON")
        
        # Get the route handler
        router = self.endpoint.create_rest_api_route()
        handler = router.routes[0].endpoint
        
        # Act
        response = await handler(mock_request)
        
        # Assert
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 500)
        content = response.body.decode()
        self.assertIn("error", content)
        self.assertIn("Invalid JSON", content)


class TestTelegramWebhookEndpoint(unittest.TestCase):
    """Test suite for TelegramWebhookEndpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.telegram_webhook_use_case = AsyncMock()
        self.endpoint = TelegramWebhookEndpoint(
            telegram_webhook_use_case=self.telegram_webhook_use_case
        )
        
        # Set up a success response
        self.telegram_webhook_use_case.process_update.return_value = WebhookResponse(
            status="success",
            message="Update processed successfully"
        )
    
    def test_create_rest_api_route(self):
        """Test creating the API router."""
        # Act
        router = self.endpoint.create_rest_api_route()
        
        # Assert
        self.assertEqual(router.prefix, "/webhook/telegram")
        self.assertEqual(router.tags, ["Webhooks"])
        self.assertTrue(hasattr(router, "routes"))
        self.assertEqual(len(router.routes), 1)  # Should have one POST route
    
    async def test_a_telegram_webhook_success(self):
        """Test successful update processing."""
        # Arrange
        mock_request = AsyncMock(spec=Request)
        mock_request.json.return_value = {
            "update_id": 12345,
            "message": {"text": "Hello"}
        }
        
        # Get the route handler
        router = self.endpoint.create_rest_api_route()
        handler = router.routes[0].endpoint
        
        # Act
        response = await handler(mock_request)
        
        # Assert
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 200)
        content = response.body.decode()
        self.assertIn("success", content)
        self.assertIn("Update processed successfully", content)
        self.telegram_webhook_use_case.process_update.assert_called_once_with(
            {"update_id": 12345, "message": {"text": "Hello"}}
        )
    
    async def test_a_telegram_webhook_request_error(self):
        """Test error handling when request parsing fails."""
        # Arrange
        mock_request = AsyncMock(spec=Request)
        mock_request.json.side_effect = Exception("Invalid JSON")
        
        # Get the route handler
        router = self.endpoint.create_rest_api_route()
        handler = router.routes[0].endpoint
        
        # Act
        response = await handler(mock_request)
        
        # Assert
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 500)
        content = response.body.decode()
        self.assertIn("error", content)
        self.assertIn("Invalid JSON", content)
