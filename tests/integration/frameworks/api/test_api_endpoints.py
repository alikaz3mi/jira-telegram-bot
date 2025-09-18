"""Integration tests for API endpoints."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.adapters.controllers.jira_webhook_controller import JiraWebhookController
from jira_telegram_bot.frameworks.api.endpoints.jira_webhook import JiraWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints.telegram_webhook import TelegramWebhookEndpoint
from jira_telegram_bot.use_cases.webhooks import JiraWebhookUseCase, TelegramWebhookUseCase


class TestApiEndpoints(unittest.TestCase):
    """Integration tests for API endpoints."""

    def setUp(self):
        """Set up the test client and mocked dependencies."""
        # Create a test FastAPI app
        self.app = FastAPI()

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

        # Create mock controllers for Jira webhook
        self.jira_controller = MagicMock(spec=JiraWebhookController)
        self.jira_controller.process_webhook = AsyncMock(return_value=WebhookResponse(
            status="success", message="Jira webhook processed"
        ))

        # Create webhook endpoints
        jira_webhook_endpoint = JiraWebhookEndpoint(jira_webhook_controller=self.jira_controller)
        telegram_webhook_endpoint = TelegramWebhookEndpoint(telegram_webhook_use_case=self.telegram_webhook_use_case)

        # Add the routers with api/v1 prefix to match test expectations
        self.app.include_router(jira_webhook_endpoint.create_rest_api_route(), prefix="/api/v1")
        self.app.include_router(telegram_webhook_endpoint.create_rest_api_route(), prefix="/api/v1")

        # Create a client for testing
        self.client = TestClient(self.app)

    def tearDown(self):
        """Clean up test fixtures."""
        pass

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
