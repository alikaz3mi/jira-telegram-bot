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
        # Patch the dependency injection to use mocks
        cls.container_patcher = patch.object(
            app_container, 'get_container', return_value=app_container.setup_container()
        )
        cls.container_patcher.start()
        
        # Create a test client
        cls.client = TestClient(app)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are run."""
        cls.container_patcher.stop()
    
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
            "/webhook/jira/",
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
            "/webhook/telegram/",
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
            "/webhook/jira/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Even with invalid payload, the endpoint should process it and return 200
        # with an appropriate status in the response body
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "ignored")
    
    def test_invalid_telegram_payload(self):
        """Test the Telegram webhook endpoint with invalid payload."""
        # Invalid payload (missing required fields)
        payload = {
            "random_field": "random_value"
        }
        
        # Send a request to the endpoint
        response = self.client.post(
            "/webhook/telegram/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Even with invalid payload, the endpoint should handle it gracefully
        # and return an appropriate response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["ignored", "error"])


if __name__ == "__main__":
    unittest.main()
