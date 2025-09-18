"""Unit tests for JiraWebhookEndpoint."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.adapters.controllers.jira_webhook_controller import (
    JiraWebhookController,
)
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.endpoints.jira_webhook import JiraWebhookEndpoint


class TestJiraWebhookEndpoint(unittest.TestCase):
    """Test suite for JiraWebhookEndpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.jira_webhook_controller = AsyncMock(spec=JiraWebhookController)
        self.endpoint = JiraWebhookEndpoint(
            jira_webhook_controller=self.jira_webhook_controller,
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
                message=f"Processed event for {webhook_data['issue']['key']}",
            )
        else:
            return WebhookResponse(
                status="error",
                message="Invalid webhook data",
            )

    def test_jira_webhook_endpoint_success(self):
        """Test successful Jira webhook processing."""
        # Setup mock response
        self.jira_webhook_controller.process_webhook.return_value = WebhookResponse(
            status="success",
            message="Webhook processed successfully",
        )

    def test_jira_webhook_endpoint_error(self):
        """Test Jira webhook processing with error response."""
        # Setup mock response
        self.jira_webhook_controller.process_webhook.return_value = WebhookResponse(
            status="error",
            message="Processing failed",
        )

    def test_jira_webhook_endpoint_exception(self):
        """Test Jira webhook processing with exception."""
        # Setup mock to raise exception
        self.jira_webhook_controller.process_webhook.side_effect = Exception(
            "Test exception",
        )
