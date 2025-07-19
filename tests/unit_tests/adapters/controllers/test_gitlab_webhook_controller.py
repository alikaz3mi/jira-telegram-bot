"""Test suite for GitlabWebhookController."""

import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.adapters.controllers.gitlab_webhook_controller import GitlabWebhookController


class TestGitlabWebhookController(unittest.IsolatedAsyncioTestCase):
    """Test suite for GitlabWebhookController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.process_gitlab_event_use_case = AsyncMock()
        
        self.controller = GitlabWebhookController(
            process_gitlab_event_use_case=self.process_gitlab_event_use_case
        )
    
    async def test_a_process_webhook_push_success(self):
        """Test successful push webhook processing."""
        # Arrange
        webhook_data = {
            "object_kind": "push",
            "project": {"name": "test-project"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix bug",
                    "author": {"email": "dev@example.com"}
                }
            ]
        }
        
        self.process_gitlab_event_use_case.process_gitlab_webhook.return_value = True
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("push event", result.message)
        self.assertIn("test-project", result.message)
        
        self.process_gitlab_event_use_case.process_gitlab_webhook.assert_called_once_with(webhook_data)
    
    async def test_a_process_webhook_merge_request_success(self):
        """Test successful merge request webhook processing."""
        # Arrange
        webhook_data = {
            "object_kind": "merge_request",
            "project": {"name": "test-project"},
            "object_attributes": {
                "id": 123,
                "action": "open",
                "state": "opened"
            }
        }
        
        self.process_gitlab_event_use_case.process_gitlab_webhook.return_value = True
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("merge_request event", result.message)
        self.assertIn("test-project", result.message)
    
    async def test_a_process_webhook_no_object_kind(self):
        """Test webhook processing with no object_kind."""
        # Arrange
        webhook_data = {
            "project": {"name": "test-project"}
        }
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("No object_kind found", result.message)
        
        self.process_gitlab_event_use_case.process_gitlab_webhook.assert_not_called()
    
    async def test_a_process_webhook_no_project_info(self):
        """Test webhook processing with no project information."""
        # Arrange
        webhook_data = {
            "object_kind": "push"
        }
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("No project information found", result.message)
    
    async def test_a_process_webhook_push_no_commits(self):
        """Test push webhook processing with no commits."""
        # Arrange
        webhook_data = {
            "object_kind": "push",
            "project": {"name": "test-project"},
            "commits": []
        }
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("No commits found", result.message)
    
    async def test_a_process_webhook_mr_no_attributes(self):
        """Test merge request webhook processing with no attributes."""
        # Arrange
        webhook_data = {
            "object_kind": "merge_request",
            "project": {"name": "test-project"}
        }
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("No merge request data found", result.message)
    
    async def test_a_process_webhook_processing_failed(self):
        """Test webhook processing when use case fails."""
        # Arrange
        webhook_data = {
            "object_kind": "push",
            "project": {"name": "test-project"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix bug",
                    "author": {"email": "dev@example.com"}
                }
            ]
        }
        
        self.process_gitlab_event_use_case.process_gitlab_webhook.return_value = False
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "error")
        self.assertIn("Failed to process", result.message)
    
    async def test_a_process_webhook_exception_handling(self):
        """Test webhook processing with exception handling."""
        # Arrange
        webhook_data = {
            "object_kind": "push",
            "project": {"name": "test-project"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix bug",
                    "author": {"email": "dev@example.com"}
                }
            ]
        }
        
        self.process_gitlab_event_use_case.process_gitlab_webhook.side_effect = Exception("Test error")
        
        # Act
        result = await self.controller.process_webhook(webhook_data)
        
        # Assert
        self.assertEqual(result.status, "error")
        self.assertIn("Error processing webhook", result.message)
