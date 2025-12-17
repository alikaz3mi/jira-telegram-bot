"""Test suite for JiraWebhookController."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from jira_telegram_bot.adapters.controllers.jira_webhook_controller import JiraWebhookController
from jira_telegram_bot.entities.api_schemas import WebhookResponse


class TestJiraWebhookController(unittest.IsolatedAsyncioTestCase):
    """Test suite for JiraWebhookController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.jira_webhook_use_case = AsyncMock()
        self.process_jira_event_use_case = AsyncMock()
        
        self.controller = JiraWebhookController(
            jira_webhook_use_case=self.jira_webhook_use_case,
            process_jira_event_use_case=self.process_jira_event_use_case
        )
    
    async def test_a_process_webhook_success(self):
        """Test successful webhook processing."""
        # Arrange
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "TEST-123"},
            "user": {"displayName": "Test User"}
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="success",
            message="Notification processed"
        )
        self.process_jira_event_use_case.process_jira_webhook.return_value = True
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("TEST-123", result.message)
        self.assertIn("Notification: Notification processed", result.message)
        self.assertIn("Metrics: Successfully processed", result.message)
        
        self.jira_webhook_use_case.process_webhook.assert_called_once_with(webhook_data)
        self.process_jira_event_use_case.process_jira_webhook.assert_called_once_with(webhook_data)
    
    async def test_a_process_webhook_invalid_data(self):
        """Test webhook processing with invalid data."""
        # Arrange
        webhook_data = {"invalid": "data"}
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("No event_type found", result.message)
        
        self.jira_webhook_use_case.process_webhook.assert_not_called()
        self.process_jira_event_use_case.process_jira_webhook.assert_not_called()
    
    async def test_a_process_webhook_missing_issue_key(self):
        """Test webhook processing with missing issue key."""
        # Arrange
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {}
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="ignored",
            message="No mapping found"
        )
        self.process_jira_event_use_case.process_jira_webhook.return_value = False
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert - Should still process even without issue key
        self.assertEqual(result.status, "ignored")
        self.assertIn("Metrics: Processing failed", result.message)
    
    async def test_a_process_webhook_metrics_failed(self):
        """Test webhook processing when metrics fails."""
        # Arrange
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "TEST-123"}
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="success",
            message="Notification processed"
        )
        self.process_jira_event_use_case.process_jira_webhook.return_value = False
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")  # Returns success when notification succeeds
        self.assertIn("Metrics: Processing failed", result.message)
    
    async def test_a_process_webhook_notification_ignored(self):
        """Test webhook processing when notification is ignored."""
        # Arrange
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "TEST-123"}
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="ignored",
            message="No mapping found"
        )
        self.process_jira_event_use_case.process_jira_webhook.return_value = True
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")  # Returns success when metrics succeeds
        self.assertIn("Notification: No mapping found", result.message)
    
    async def test_a_process_webhook_both_failed(self):
        """Test webhook processing when both processes fail."""
        # Arrange
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "TEST-123"}
        }
        
        self.jira_webhook_use_case.process_webhook.return_value = WebhookResponse(
            status="ignored",
            message="Notification ignored"
        )
        self.process_jira_event_use_case.process_jira_webhook.return_value = False
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("Notification: Notification ignored", result.message)
        self.assertIn("Metrics: Processing failed", result.message)
    
    async def test_a_process_webhook_exception_handling(self):
        """Test webhook processing with exception handling."""
        # Arrange
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "TEST-123"}
        }
        
        self.jira_webhook_use_case.process_webhook.side_effect = Exception("Test error")
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "error")
        self.assertIn("Error processing webhook", result.message)
