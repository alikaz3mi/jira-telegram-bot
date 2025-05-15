"""Unit tests for Telegram webhook use case."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update, Message, User, Chat

from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case import TelegramWebhookUseCase


class TestTelegramWebhookUseCase(unittest.TestCase):
    """Test suite for TelegramWebhookUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.create_task_use_case = AsyncMock()
        self.parse_prompt_use_case = AsyncMock()
        self.task_manager_repository = MagicMock()
        
        self.use_case = TelegramWebhookUseCase(
            create_task_use_case=self.create_task_use_case,
            parse_prompt_use_case=self.parse_prompt_use_case,
            task_manager_repository=self.task_manager_repository
        )
        
        # Set up patches
        self.patch_get_issue_key = patch(
            "jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case.get_issue_key_from_channel_post"
        )
        self.mock_get_issue_key = self.patch_get_issue_key.start()
        
        self.patch_save_mapping = patch(
            "jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case.save_mapping"
        )
        self.mock_save_mapping = self.patch_save_mapping.start()
        
        self.patch_save_comment = patch(
            "jira_telegram_bot.use_cases.webhooks.telegram_webhook_use_case.save_comment"
        )
        self.mock_save_comment = self.patch_save_comment.start()
        
        # Default values
        self.parse_prompt_use_case.run.return_value = {
            "project_key": "TEST",
            "summary": "Test Task",
            "components": ["Backend"],
            "labels": ["bug"]
        }
        
        self.create_task_use_case.execute_task_creation.return_value = MagicMock(key="TEST-123")
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.patch_get_issue_key.stop()
        self.patch_save_mapping.stop()
        self.patch_save_comment.stop()
    
    async def test_a_invalid_update_data(self):
        """Test processing invalid update data."""
        # Arrange
        update_data = {}
        
        # Mock Update.de_json to return None
        with patch("telegram.Update.de_json", return_value=None):
            # Act
            result = await self.use_case.process_update(update_data)
        
        # Assert
        self.assertEqual(result.status, "error")
        self.assertEqual(result.message, "Invalid update data")
    
    async def test_a_handle_channel_post(self):
        """Test handling a channel post (creating a task)."""
        # Arrange
        channel_post = MagicMock(
            chat_id=123456789,
            message_id=987654321,
            text="Create a new task"
        )
        update = MagicMock(
            channel_post=channel_post,
            message=None
        )
        
        # Act
        with patch("telegram.Update.de_json", return_value=update):
            result = await self.use_case.process_update({})
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("Created issue", result.message)
        self.create_task_use_case.execute_task_creation.assert_called_once()
        self.mock_save_mapping.assert_called_once()
    
    async def test_a_handle_reply_to_channel_post(self):
        """Test handling a reply to a channel post (adding a comment)."""
        # Arrange
        chat = MagicMock(id=123456789)
        user = MagicMock(
            username="test_user",
            first_name="Test"
        )
        reply_to_message = MagicMock(
            chat_id=123456789,
            message_id=987654321
        )
        message = MagicMock(
            chat=chat,
            message_id=111222333,
            from_user=user,
            reply_to_message=reply_to_message,
            text="This is a comment"
        )
        update = MagicMock(
            channel_post=None,
            message=message
        )
        
        # Set up issue key lookup
        self.mock_get_issue_key.return_value = "TEST-123"
        
        # Act
        with patch("telegram.Update.de_json", return_value=update):
            result = await self.use_case.process_update({})
        
        # Assert
        self.assertEqual(result.status, "success")
        self.assertIn("Added comment", result.message)
        self.task_manager_repository.add_comment.assert_called_once()
        self.mock_save_comment.assert_called_once()
    
    async def test_a_handle_reply_no_issue_key(self):
        """Test handling a reply with no associated issue."""
        # Arrange
        chat = MagicMock(id=123456789)
        user = MagicMock(
            username="test_user",
            first_name="Test"
        )
        reply_to_message = MagicMock(
            chat_id=123456789,
            message_id=987654321
        )
        message = MagicMock(
            chat=chat,
            message_id=111222333,
            from_user=user,
            reply_to_message=reply_to_message,
            text="This is a comment"
        )
        update = MagicMock(
            channel_post=None,
            message=message
        )
        
        # No issue key found for the channel post
        self.mock_get_issue_key.return_value = None
        
        # Act
        with patch("telegram.Update.de_json", return_value=update):
            result = await self.use_case.process_update({})
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertEqual(result.message, "No associated issue found")
        self.task_manager_repository.add_comment.assert_not_called()
        self.mock_save_comment.assert_not_called()
    
    async def test_a_handle_direct_message(self):
        """Test handling a direct message to the bot."""
        # Arrange
        message = MagicMock(
            reply_to_message=None,
            text="Hello bot"
        )
        update = MagicMock(
            channel_post=None,
            message=message
        )
        
        # Act
        with patch("telegram.Update.de_json", return_value=update):
            result = await self.use_case.process_update({})
        
        # Assert
        self.assertEqual(result.status, "ignored")
        self.assertIn("Direct messages", result.message)
        self.create_task_use_case.execute_task_creation.assert_not_called()
        self.task_manager_repository.add_comment.assert_not_called()
