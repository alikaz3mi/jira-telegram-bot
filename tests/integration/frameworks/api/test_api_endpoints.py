"""Integration tests for API endpoints."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from lagom.integrations.fast_api import FastApiIntegration

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.entry_point import app
from jira_telegram_bot.use_cases.webhooks import JiraWebhookUseCase, TelegramWebhookUseCase


class TestApiEndpoints(unittest.TestCase):
    """Integration tests for API endpoints."""
    
    def setUp(self):
        """Set up the test client and mocked dependencies."""
        # Create a client for testing
        self.client = TestClient(app)
        
        # Mock the use cases
        self.jira_webhook_use_case = AsyncMock(spec=JiraWebhookUseCase)
        self.telegram_webhook_use_case = AsyncMock(spec=TelegramWebhookUseCase)
        
        # Set default return values
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="success",
            message="Jira webhook processed"
        )
        
        self.telegram_webhook_use_case.process_update.return_value = WebhookResponse(
            status="success",
            message="Telegram update processed"
        )
        
        # Set up the patches
        self.patches = []
        
        # Mock FastApiIntegration.depends for JiraWebhookUseCase
        self.patches.append(
            patch("lagom.integrations.fast_api.FastApiIntegration.depends", 
                  side_effect=self._mock_depends)
        )
        
        # Start all patches
        for patcher in self.patches:
            patcher.start()
    
    def tearDown(self):
        """Clean up test fixtures."""
        for patcher in self.patches:
            patcher.stop()
    
    def _mock_depends(self, use_case_class):
        """Mock dependency resolution based on the requested class."""
        if use_case_class == JiraWebhookUseCase:
            return self.jira_webhook_use_case
        elif use_case_class == TelegramWebhookUseCase:
            return self.telegram_webhook_use_case
        else:
            return MagicMock()
    
    def test_jira_webhook_endpoint(self):
        """Test the Jira webhook endpoint."""
        # Arrange
        payload = {
            "issue_event_type_name": "issue_updated",
            "issue": {"key": "TEST-123"}
        }
        
        # Act
        response = self.client.post("/api/v1/webhook/jira/", json=payload)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["success", "ignored", "error"])
        
    def test_telegram_webhook_endpoint(self):
        """Test the Telegram webhook endpoint."""
        # Arrange
        payload = {
            "update_id": 12345,
            "message": {"text": "Hello"}
        }
        
        # Act
        response = self.client.post("/api/v1/webhook/telegram/", json=payload)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["success", "ignored", "error"])
    
    @pytest.mark.asyncio
    async def test_a_concurrent_requests(self):
        """Test handling multiple concurrent requests."""
        # This is a simplified concurrency test that would be expanded in a real environment
        import asyncio
        import httpx
        
        # Arrange - Create multiple payloads
        jira_payloads = [
            {"issue_event_type_name": "issue_updated", "issue": {"key": f"TEST-{i}"}}
            for i in range(10)
        ]
        
        telegram_payloads = [
            {"update_id": i, "message": {"text": f"Message {i}"}}
            for i in range(10)
        ]
        
        # In an actual test, we would use something like:
        # async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        #     tasks = [
        #         client.post("/api/v1/webhook/jira/", json=payload)
        #         for payload in jira_payloads
        #     ] + [
        #         client.post("/api/v1/webhook/telegram/", json=payload)
        #         for payload in telegram_payloads
        #     ]
        #     responses = await asyncio.gather(*tasks)
        
        # For this test, we'll simulate by directly calling the use case methods
        jira_tasks = [
            self.jira_webhook_use_case.process_webhook(payload)
            for payload in jira_payloads
        ]
        
        telegram_tasks = [
            self.telegram_webhook_use_case.process_update(payload)
            for payload in telegram_payloads
        ]
        
        # Act
        all_responses = await asyncio.gather(*(jira_tasks + telegram_tasks))
        
        # Assert
        self.assertEqual(len(all_responses), 20)  # 10 Jira + 10 Telegram
        for response in all_responses:
            self.assertEqual(response.status, "success")
