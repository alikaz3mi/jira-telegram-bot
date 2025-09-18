"""Test suite for BaseWebhookController."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.adapters.controllers.base_webhook_controller import (
    BaseWebhookController,
)
from jira_telegram_bot.entities.api_schemas import WebhookResponse


class TestBaseWebhookController(BaseWebhookController):
    """Test implementation of BaseWebhookController."""

    def __init__(self):
        super().__init__()
        self.validate_webhook_data_mock = unittest.mock.Mock()
        self.route_to_use_case_mock = AsyncMock()

    def _validate_webhook_data(self, webhook_data):
        """Mock validation."""
        return self.validate_webhook_data_mock(webhook_data)

    async def _route_to_use_case(self, webhook_data):
        """Mock routing."""
        return await self.route_to_use_case_mock(webhook_data)


class TestBaseWebhookControllerUnit(unittest.IsolatedAsyncioTestCase):
    """Test suite for BaseWebhookController."""

    def setUp(self):
        """Set up test fixtures."""
        self.controller = TestBaseWebhookController()

    async def test_a_process_webhook_success(self):
        """Test successful webhook processing."""
        # Arrange
        webhook_data = {"test": "data"}

        self.controller.validate_webhook_data_mock.return_value = None
        self.controller.route_to_use_case_mock.return_value = WebhookResponse(
            status="success",
            message="Processed successfully",
        )

        # Act
        result = await self.controller.process_webhook(webhook_data)

        # Assert
        self.assertEqual(result.status, "success")
        self.assertEqual(result.message, "Processed successfully")

        self.controller.validate_webhook_data_mock.assert_called_once_with(webhook_data)
        self.controller.route_to_use_case_mock.assert_called_once_with(webhook_data)

    async def test_a_process_webhook_validation_failure(self):
        """Test webhook processing with validation failure."""
        # Arrange
        webhook_data = {"test": "data"}
        validation_error = WebhookResponse(
            status="ignored",
            message="Validation failed",
        )

        self.controller.validate_webhook_data_mock.return_value = validation_error

        # Act
        result = await self.controller.process_webhook(webhook_data)

        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertEqual(result.message, "Validation failed")

        self.controller.validate_webhook_data_mock.assert_called_once_with(webhook_data)
        self.controller.route_to_use_case_mock.assert_not_called()

    async def test_a_process_webhook_exception_handling(self):
        """Test webhook processing with exception handling."""
        # Arrange
        webhook_data = {"test": "data"}

        self.controller.validate_webhook_data_mock.side_effect = Exception("Test error")

        # Act
        result = await self.controller.process_webhook(webhook_data)

        # Assert
        self.assertEqual(result.status, "error")
        self.assertIn("Error processing webhook", result.message)
        self.assertIn("Test error", result.message)

    def test_extract_basic_info(self):
        """Test extracting basic information from webhook data."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_created",
            "issue": {"key": "TEST-123"},
            "timestamp": "2023-01-01T00:00:00Z",
            "webhookEvent": "jira:issue_created",
        }

        # Act
        result = self.controller._extract_basic_info(webhook_data)

        # Assert
        self.assertEqual(result["event_type"], "issue_created")
        self.assertEqual(result["issue_key"], "TEST-123")
        self.assertEqual(result["timestamp"], "2023-01-01T00:00:00Z")
        self.assertEqual(result["webhook_id"], "jira:issue_created")

    def test_create_success_response(self):
        """Test creating success response."""
        # Act
        result = self.controller._create_success_response("Test message")

        # Assert
        self.assertEqual(result.status, "success")
        self.assertEqual(result.message, "Test message")

    def test_create_ignored_response(self):
        """Test creating ignored response."""
        # Act
        result = self.controller._create_ignored_response("Test message")

        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertEqual(result.message, "Test message")

    def test_create_error_response(self):
        """Test creating error response."""
        # Act
        result = self.controller._create_error_response("Test message")

        # Assert
        self.assertEqual(result.status, "error")
        self.assertEqual(result.message, "Test message")
