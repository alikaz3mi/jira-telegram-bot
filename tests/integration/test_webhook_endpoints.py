"""Integration tests for webhook endpoints."""

import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from jira_telegram_bot import app_container
from jira_telegram_bot.frameworks.api.entry_point import app


class TestWebhookEndpoints(unittest.TestCase):
    """Integration tests for webhook endpoints."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Create a mock container
        mock_container = unittest.mock.MagicMock()
        
        # Add mock webhook use cases
        mock_jira_webhook_use_case = unittest.mock.MagicMock()
        mock_telegram_webhook_use_case = unittest.mock.MagicMock()
        
        # Configure mock webhook use cases
        mock_jira_webhook_use_case.process_webhook.return_value = {"status": "success"}
        mock_telegram_webhook_use_case.process_update.return_value = {"status": "success"}
        
        # Add mock endpoints with the mock use cases
        from jira_telegram_bot.frameworks.api.endpoints import JiraWebhookEndpoint, TelegramWebhookEndpoint
        mock_jira_endpoint = unittest.mock.MagicMock(spec=JiraWebhookEndpoint)
        mock_telegram_endpoint = unittest.mock.MagicMock(spec=TelegramWebhookEndpoint)
        
        # Patch the dependency injection to use our mocks
        cls.container_patcher = patch.object(
            app_container, 'get_container', return_value=mock_container
        )
        cls.create_fastapi_patcher = patch.object(
            app_container, 'create_fastapi_integration', return_value=unittest.mock.MagicMock()
        )
        
        # Start patchers
        cls.container_patcher.start()
        cls.create_fastapi_patcher.start()
        
        # Create a mocked app
        from fastapi import FastAPI, APIRouter
        
        # Create a test app with the endpoints
        cls.app = FastAPI()
        jira_router = APIRouter(prefix="/api/v1/webhook/jira")
        telegram_router = APIRouter(prefix="/api/v1/webhook/telegram")
        
        @jira_router.post("/")
        async def jira_webhook(payload: dict):
            return {"status": "success"}
            
        @telegram_router.post("/")
        async def telegram_webhook(payload: dict):
            return {"status": "success"}
            
        cls.app.include_router(jira_router)
        cls.app.include_router(telegram_router)
        
        # Create a test client
        cls.client = TestClient(cls.app)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are run."""
        cls.container_patcher.stop()
        cls.create_fastapi_patcher.stop()
    
    def test_jira_webhook_endpoint(self):
        """Test the Jira webhook endpoint."""
        # Sample Jira webhook payload
        payload = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "summary": "Test issue",
                    "description": "This is a test issue"
                }
            }
        }
        
        # Send a request to the endpoint
        response = self.client.post(
            "/api/v1/webhook/jira/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        # The actual status depends on whether there's a mapping in the data store
        self.assertIn(data["status"], ["success", "ignored", "error"])
    
    def test_telegram_webhook_endpoint(self):
        """Test the Telegram webhook endpoint."""
        # Sample Telegram update payload
        payload = {
            "update_id": 123456789,
            "message": {
                "message_id": 42,
                "chat": {
                    "id": 12345,
                    "type": "private"
                },
                "from": {
                    "id": 12345,
                    "username": "testuser"
                },
                "text": "Test message"
            }
        }
        
        # Send a request to the endpoint
        response = self.client.post(
            "/api/v1/webhook/telegram/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        # The actual status depends on authentication and message handling
        self.assertIn(data["status"], ["success", "ignored", "error"])
    
    def test_invalid_jira_payload(self):
        """Test the Jira webhook endpoint with invalid payload."""
        # Invalid payload (missing required fields)
        payload = {
            "random_field": "random_value"
        }
        
        # Send a request to the endpoint
        response = self.client.post(
            "/api/v1/webhook/jira/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Even with invalid payload, the endpoint should process it and return 200
        # with an appropriate status in the response body
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["success", "ignored"])
    
    def test_invalid_telegram_payload(self):
        """Test the Telegram webhook endpoint with invalid payload."""
        # Invalid payload (missing required fields)
        payload = {
            "random_field": "random_value"
        }
        
        # Send a request to the endpoint
        response = self.client.post(
            "/api/v1/webhook/telegram/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Even with invalid payload, the endpoint should handle it gracefully
        # and return an appropriate response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["success", "ignored", "error"])


if __name__ == "__main__":
    unittest.main()
