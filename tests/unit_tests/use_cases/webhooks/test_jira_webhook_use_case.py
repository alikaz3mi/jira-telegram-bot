"""Unit tests for Jira webhook use case."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case import JiraWebhookUseCase


class TestJiraWebhookUseCase(unittest.TestCase):
    """Test suite for JiraWebhookUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.jira_settings = MagicMock()
        self.telegram_gateway = AsyncMock()
        self.use_case = JiraWebhookUseCase(
            jira_settings=self.jira_settings,
            telegram_gateway=self.telegram_gateway
        )
        
        # Patch the get_mapping_by_issue_key function
        self.patcher = patch(
            "jira_telegram_bot.use_cases.webhooks.jira_webhook_use_case.get_mapping_by_issue_key"
        )
        self.mock_get_mapping = self.patcher.start()
        
        # Default mapping for tests
        self.mock_get_mapping.return_value = {
            "channel_chat_id": "123456789",
            "message_id": "987654321",
            "group_chat_id": "111222333"
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.patcher.stop()
    
    async def test_a_process_webhook_invalid_data(self):
        """Test processing webhook with invalid data."""
        # Arrange
        webhook_data = {}
        
        # Act
        result = await self.use_case.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertEqual(result.message, "No issue_key or event_type found")
    
    async def test_a_process_webhook_no_mapping(self):
        """Test processing webhook with no mapping found."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_updated",
            "issue": {"key": "TEST-123"}
        }
        self.mock_get_mapping.return_value = None
        
        # Act
        result = await self.use_case.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertEqual(result.message, "No matching issue_key in local data")
        
    async def test_a_process_webhook_comment_event(self):
        """Test processing a comment event."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_commented",
            "issue": {"key": "TEST-123"},
            "comment": {
                "body": "This is a test comment",
                "author": {"displayName": "Test User"}
            }
        }
        
        # Act
        result = await self.use_case.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("issue_commented", result.message)
        self.telegram_gateway.send_message.assert_called_once()
        
    async def test_a_process_webhook_status_change(self):
        """Test processing a status change event."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_updated",
            "issue": {"key": "TEST-123"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "In Progress",
                        "toString": "Done"
                    }
                ]
            }
        }
        
        # Act
        result = await self.use_case.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("issue_updated", result.message)
        self.telegram_gateway.send_message.assert_called_once()
        
    async def test_a_process_webhook_exception(self):
        """Test exception handling during webhook processing."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_commented",
            "issue": {"key": "TEST-123"}
        }
        self.telegram_gateway.send_message.side_effect = Exception("Test error")
        
        # Act
        result = await self.use_case.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "error")
        self.assertIn("Error processing webhook", result.message)
