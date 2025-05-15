"""Unit tests for JiraWebhookEndpoint."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.endpoints.jira_webhook import JiraWebhookEndpoint
from jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case import JiraWebhookUseCase


class TestJiraWebhookEndpoint(unittest.TestCase):
    """Test suite for JiraWebhookEndpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.jira_webhook_use_case = AsyncMock(spec=JiraWebhookUseCase)
        self.endpoint = JiraWebhookEndpoint(
            jira_webhook_use_case=self.jira_webhook_use_case
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
        self.assertEqual(router.prefix, "/webhook/jira")
        self.assertEqual(router.tags, ["Webhooks"])
    
    async def _mock_process_webhook(self, webhook_data):
        """Mock for jira_webhook_use_case.process_webhook."""
        if "issue" in webhook_data and "key" in webhook_data["issue"]:
            return WebhookResponse(
                status="success",
                message=f"Processed event for {webhook_data['issue']['key']}"
            )
        else:
            return WebhookResponse(
                status="error",
                message="Invalid webhook data"
            )
    
    def test_jira_webhook_endpoint_success(self):
        """Test successful webhook processing."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_updated",
            "issue": {"key": "PROJ-123"}
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="success",
            message="Processed event for PROJ-123"
        )
        
        # Act
        with patch('fastapi.Request.json', AsyncMock(return_value=webhook_data)):
            response = self.client.post("/webhook/jira/", json=webhook_data)
        
        # Assert
        self.jira_webhook_use_case.process_webhook.assert_called_once_with(webhook_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), 
            {"status": "success", "message": "Processed event for PROJ-123"}
        )
    
    def test_jira_webhook_endpoint_error(self):
        """Test error handling in webhook processing."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_updated"
            # Missing issue key
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="error",
            message="Invalid webhook data"
        )
        
        # Act
        with patch('fastapi.Request.json', AsyncMock(return_value=webhook_data)):
            response = self.client.post("/webhook/jira/", json=webhook_data)
        
        # Assert
        self.jira_webhook_use_case.process_webhook.assert_called_once_with(webhook_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), 
            {"status": "error", "message": "Invalid webhook data"}
        )
    
    def test_jira_webhook_endpoint_exception(self):
        """Test exception handling in webhook processing."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_updated",
            "issue": {"key": "PROJ-123"}
        }
        
        self.jira_webhook_use_case.process_webhook.side_effect = Exception("Test exception")
        
        # Act
        with patch('fastapi.Request.json', AsyncMock(return_value=webhook_data)):
            response = self.client.post("/webhook/jira/", json=webhook_data)
        
        # Assert
        self.jira_webhook_use_case.process_webhook.assert_called_once_with(webhook_data)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(), 
            {"status": "error", "message": "Error: Test exception"}
        )
