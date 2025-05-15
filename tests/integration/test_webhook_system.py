"""System test for webhook infrastructure."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.frameworks.api.entry_point import app


class TestWebhookSystem(unittest.TestCase):
    """System test for webhook infrastructure."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        cls.client = TestClient(app)
        
        # Mock the container and dependencies
        cls.container = get_container()
        
        # Store originals
        cls.original_jira_webhook_use_case = cls.container.resolve(
            "jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case.JiraWebhookUseCase"
        )
        cls.original_telegram_webhook_use_case = cls.container.resolve(
            "jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case.TelegramWebhookUseCase"
        )
        
        # Create mocks
        cls.jira_webhook_use_case_mock = AsyncMock()
        cls.telegram_webhook_use_case_mock = AsyncMock()
        
        # Configure the mocks
        cls.jira_webhook_use_case_mock.process_webhook = AsyncMock()
        cls.telegram_webhook_use_case_mock.process_update = AsyncMock()
        
        # Replace the originals with mocks
        cls.container.partial_reset({
            "jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case.JiraWebhookUseCase": 
                cls.jira_webhook_use_case_mock,
            "jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case.TelegramWebhookUseCase": 
                cls.telegram_webhook_use_case_mock
        })
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are run."""
        # Restore the original use cases
        cls.container.partial_reset({
            "jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case.JiraWebhookUseCase": 
                cls.original_jira_webhook_use_case,
            "jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case.TelegramWebhookUseCase": 
                cls.original_telegram_webhook_use_case
        })
    
    def test_health_endpoint(self):
        """Test health endpoint."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
    
    def test_health_ping_endpoint(self):
        """Test health ping endpoint."""
        response = self.client.get("/health/ping")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ping"], "pong")
    
    def test_jira_webhook_endpoint(self):
        """Test Jira webhook endpoint."""
        # Configure mock
        self.jira_webhook_use_case_mock.process_webhook.return_value = MagicMock(
            dict=lambda: {"status": "success", "message": "Processed jira webhook"}
        )
        
        # Send request
        payload = {"issue_event_type_name": "issue_created", "issue": {"key": "TEST-123"}}
        response = self.client.post("/webhook/jira/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Processed jira webhook")
        
        # Verify use case was called correctly
        self.jira_webhook_use_case_mock.process_webhook.assert_called_once_with(payload)
    
    def test_telegram_webhook_endpoint(self):
        """Test Telegram webhook endpoint."""
        # Configure mock
        self.telegram_webhook_use_case_mock.process_update.return_value = MagicMock(
            dict=lambda: {"status": "success", "message": "Processed telegram update"}
        )
        
        # Send request
        payload = {"update_id": 123456789, "message": {"text": "Test message"}}
        response = self.client.post("/webhook/telegram/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Processed telegram update")
        
        # Verify use case was called correctly
        self.telegram_webhook_use_case_mock.process_update.assert_called_once_with(payload)
    
    def test_jira_webhook_error(self):
        """Test Jira webhook endpoint error handling."""
        # Configure mock to raise exception
        self.jira_webhook_use_case_mock.process_webhook.side_effect = Exception("Test error")
        
        # Send request
        payload = {"issue_event_type_name": "issue_created", "issue": {"key": "TEST-123"}}
        response = self.client.post("/webhook/jira/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Error: Test error")
    
    def test_telegram_webhook_error(self):
        """Test Telegram webhook endpoint error handling."""
        # Configure mock to raise exception
        self.telegram_webhook_use_case_mock.process_update.side_effect = Exception("Test error")
        
        # Send request
        payload = {"update_id": 123456789, "message": {"text": "Test message"}}
        response = self.client.post("/webhook/telegram/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Error: Test error")


if __name__ == "__main__":
    unittest.main()
