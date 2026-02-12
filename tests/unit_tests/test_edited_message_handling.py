"""Unit tests for Telegram message editing functionality.

Tests the complete flow:
1. Comment creation stores telegram_message_id -> jira_comment_id mapping
2. Message edits look up the exact comment to update
3. Jira comment is updated with edited text
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from jira_telegram_bot.frameworks.fast_api.create_ticket import (
    handle_group_comment,
    handle_edited_message,
)


class TestEditedMessageHandling(unittest.IsolatedAsyncioTestCase):
    """Test suite for message editing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_message = {
            "message_id": 12345,
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "from": {"username": "test_user", "id": 987654321},
            "text": "This is a test comment",
            "reply_to_message": {
                "message_id": 7987,
                "forward_from_message_id": 5555
            }
        }
        
        self.edited_message = {
            "message_id": 12345,  # Same message ID as original
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "from": {"username": "test_user", "id": 987654321},
            "text": "This is an EDITED test comment",  # Changed text
            "edit_date": 1699876543
        }

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository")
    async def test_acomment_creation_stores_mapping(
        self, mock_jira_repo, mock_user_config, mock_data_store
    ):
        """Test that creating a comment stores the telegram<->jira mapping."""
        # Setup mocks
        mock_user_cfg = MagicMock()
        mock_user_cfg.jira_username = "test_jira_user"
        mock_user_config.get_user_config.return_value = mock_user_cfg
        
        mock_data_store.find_issue_key_from_message_id.return_value = "PROJ1-123"
        mock_data_store.load_data_store.return_value = {}
        
        # Mock the comment creation to return a comment with ID
        mock_comment = MagicMock()
        mock_comment.id = "10001"
        mock_jira_repo.add_comment.return_value = mock_comment
        
        # Call handle_group_comment
        result = await handle_group_comment(self.sample_message)
        
        # Verify store_comment_mapping was called with correct parameters
        mock_data_store.store_comment_mapping.assert_called_once_with(
            telegram_message_id=12345,
            chat_id=-1001234567890,
            jira_comment_id="10001",
            issue_key="PROJ1-123"
        )
        
        self.assertEqual(result["status"], "success")

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository")
    async def test_aedited_message_updates_exact_comment(
        self, mock_jira_repo, mock_user_config, mock_data_store
    ):
        """Test that editing a message updates the exact Jira comment."""
        # Setup mocks
        mock_user_cfg = MagicMock()
        mock_user_cfg.jira_username = "test_jira_user"
        mock_user_config.get_user_config.return_value = mock_user_cfg
        
        # Mock the stored mapping
        mock_data_store.find_comment_mapping.return_value = {
            "telegram_message_id": 12345,
            "chat_id": -1001234567890,
            "jira_comment_id": "10001",
            "issue_key": "PROJ1-123"
        }
        
        # Mock Jira API calls
        mock_issue = MagicMock()
        mock_jira_repo.jira.issue.return_value = mock_issue
        
        mock_comment = MagicMock()
        mock_comment.update = MagicMock()
        mock_jira_repo.jira.comment.return_value = mock_comment
        
        # Call handle_edited_message
        result = await handle_edited_message(self.edited_message)
        
        # Verify the correct comment was updated
        mock_jira_repo.jira.comment.assert_called_once_with("PROJ1-123", "10001")
        mock_comment.update.assert_called_once()
        
        # Check the updated body contains "edited" marker and new text
        call_args = mock_comment.update.call_args
        updated_body = call_args.kwargs['body']
        self.assertIn("edited", updated_body)
        self.assertIn("This is an EDITED test comment", updated_body)
        
        self.assertEqual(result["status"], "success")

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    async def test_aedited_message_no_mapping_found(
        self, mock_user_config, mock_data_store
    ):
        """Test handling when no stored mapping exists for edited message."""
        # Setup mocks
        mock_data_store.find_comment_mapping.return_value = None
        
        # Call handle_edited_message
        result = await handle_edited_message(self.edited_message)
        
        # Should return ignored status
        self.assertEqual(result["status"], "ignored")
        self.assertIn("No stored comment mapping", result["reason"])

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    async def test_aedited_message_no_text(self, mock_data_store):
        """Test handling edited message with no text."""
        edited_msg_no_text = {
            "message_id": 12345,
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "from": {"username": "test_user", "id": 987654321},
            # No text or caption
        }
        
        result = await handle_edited_message(edited_msg_no_text)
        
        self.assertEqual(result["status"], "ignored")
        self.assertIn("No text", result["reason"])

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository")
    async def test_aedited_message_jira_api_error(
        self, mock_jira_repo, mock_user_config, mock_data_store
    ):
        """Test handling Jira API errors during comment update."""
        # Setup mocks
        mock_user_cfg = MagicMock()
        mock_user_cfg.jira_username = "test_jira_user"
        mock_user_config.get_user_config.return_value = mock_user_cfg
        
        mock_data_store.find_comment_mapping.return_value = {
            "jira_comment_id": "10001",
            "issue_key": "PROJ1-123"
        }
        
        # Mock Jira API to raise exception
        mock_jira_repo.jira.issue.side_effect = Exception("Jira API error")
        
        result = await handle_edited_message(self.edited_message)
        
        self.assertEqual(result["status"], "error")

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository")
    async def test_aedited_anonymous_message(
        self, mock_jira_repo, mock_user_config, mock_data_store
    ):
        """Test editing a message from anonymous admin."""
        anonymous_edited = {
            "message_id": 12345,
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "from": {"username": "GroupAnonymousBot"},
            "sender_chat": {"id": -1001234567890, "type": "supergroup"},
            "text": "Edited anonymous comment",
            "edit_date": 1699876543
        }
        
        mock_data_store.find_comment_mapping.return_value = {
            "jira_comment_id": "10001",
            "issue_key": "PROJ1-123"
        }
        
        mock_comment = MagicMock()
        mock_comment.update = MagicMock()
        mock_jira_repo.jira.comment.return_value = mock_comment
        mock_jira_repo.jira.issue.return_value = MagicMock()
        
        result = await handle_edited_message(anonymous_edited)
        
        # Check that "Anonymous Admin" appears in the formatted comment
        call_args = mock_comment.update.call_args
        updated_body = call_args.kwargs['body']
        self.assertIn("Anonymous Admin", updated_body)
        self.assertIn("edited", updated_body)
        
        self.assertEqual(result["status"], "success")

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository")
    async def test_aedited_message_with_caption(
        self, mock_jira_repo, mock_user_config, mock_data_store
    ):
        """Test editing a message that has a caption (media message)."""
        edited_with_caption = {
            "message_id": 12345,
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "from": {"username": "test_user", "id": 987654321},
            "caption": "Edited caption text",  # Caption instead of text
            "photo": [{"file_id": "xyz"}],  # Has media
            "edit_date": 1699876543
        }
        
        mock_user_cfg = MagicMock()
        mock_user_cfg.jira_username = "test_jira_user"
        mock_user_config.get_user_config.return_value = mock_user_cfg
        
        mock_data_store.find_comment_mapping.return_value = {
            "jira_comment_id": "10001",
            "issue_key": "PROJ1-123"
        }
        
        mock_comment = MagicMock()
        mock_comment.update = MagicMock()
        mock_jira_repo.jira.comment.return_value = mock_comment
        mock_jira_repo.jira.issue.return_value = MagicMock()
        
        result = await handle_edited_message(edited_with_caption)
        
        # Verify caption was used
        call_args = mock_comment.update.call_args
        updated_body = call_args.kwargs['body']
        self.assertIn("Edited caption text", updated_body)
        
        self.assertEqual(result["status"], "success")


class TestDataStoreMappingMethods(unittest.TestCase):
    """Test the data store mapping storage and retrieval."""

    @patch("jira_telegram_bot.adapters.repositories.file_storage.TelegramPostDataStore.load_data_store")
    @patch("jira_telegram_bot.adapters.repositories.file_storage.TelegramPostDataStore.save_data_store")
    def test_store_comment_mapping(self, mock_save, mock_load):
        """Test storing comment mapping."""
        from jira_telegram_bot.adapters.repositories.file_storage import TelegramPostDataStore
        
        mock_load.return_value = {}
        data_store = TelegramPostDataStore()
        
        data_store.store_comment_mapping(
            telegram_message_id=12345,
            chat_id=-1001234567890,
            jira_comment_id="10001",
            issue_key="PROJ1-123"
        )
        
        # Verify save was called with correct structure
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        
        expected_key = "-1001234567890_12345_comment"
        self.assertIn(expected_key, saved_data)
        self.assertEqual(saved_data[expected_key]["jira_comment_id"], "10001")
        self.assertEqual(saved_data[expected_key]["issue_key"], "PROJ1-123")
        self.assertEqual(saved_data[expected_key]["type"], "comment_mapping")

    @patch("jira_telegram_bot.adapters.repositories.file_storage.TelegramPostDataStore.load_data_store")
    def test_find_comment_mapping(self, mock_load):
        """Test finding comment mapping."""
        from jira_telegram_bot.adapters.repositories.file_storage import TelegramPostDataStore
        
        mock_load.return_value = {
            "-1001234567890_12345_comment": {
                "telegram_message_id": 12345,
                "chat_id": -1001234567890,
                "jira_comment_id": "10001",
                "issue_key": "PROJ1-123",
                "type": "comment_mapping"
            }
        }
        
        data_store = TelegramPostDataStore()
        result = data_store.find_comment_mapping(
            telegram_message_id=12345,
            chat_id=-1001234567890
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result["jira_comment_id"], "10001")
        self.assertEqual(result["issue_key"], "PROJ1-123")

    @patch("jira_telegram_bot.adapters.repositories.file_storage.TelegramPostDataStore.load_data_store")
    def test_find_comment_mapping_not_found(self, mock_load):
        """Test finding comment mapping when it doesn't exist."""
        from jira_telegram_bot.adapters.repositories.file_storage import TelegramPostDataStore
        
        mock_load.return_value = {}
        
        data_store = TelegramPostDataStore()
        result = data_store.find_comment_mapping(
            telegram_message_id=99999,
            chat_id=-1001234567890
        )
        
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
