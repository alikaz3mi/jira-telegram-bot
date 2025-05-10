from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from jira_telegram_bot.adapters.services.telegram.authentication import TelegramAuthentication, check_user_allowed
from jira_telegram_bot.use_cases.interfaces.authentication_interface import AuthenticationInterface


class TestTelegramAuthentication(unittest.TestCase):
    """Test the TelegramAuthentication adapter implementation."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.auth_service = TelegramAuthentication()
        
        # Verify it implements the correct interface
        self.assertIsInstance(self.auth_service, AuthenticationInterface)

    @patch("jira_telegram_bot.adapters.services.telegram.authentication.TELEGRAM_SETTINGS")
    async def test_is_user_allowed_with_authorized_user(self, mock_settings: MagicMock) -> None:
        """Test user authentication with an authorized user."""
        # Arrange
        mock_settings.ALLOWED_USERS = ["test_user"]
        user_context = self._create_mock_update(username="test_user")
        
        # Act
        result = await self.auth_service.is_user_allowed(user_context)
        
        # Assert
        self.assertTrue(result)
        # Verify that reply_text was not called (no rejection message)
        user_context.message.reply_text.assert_not_called()

    @patch("jira_telegram_bot.adapters.services.telegram.authentication.TELEGRAM_SETTINGS")
    async def test_is_user_allowed_with_unauthorized_user(self, mock_settings: MagicMock) -> None:
        """Test user authentication with an unauthorized user."""
        # Arrange
        mock_settings.ALLOWED_USERS = ["authorized_user"]
        user_context = self._create_mock_update(username="unauthorized_user")
        
        # Act
        result = await self.auth_service.is_user_allowed(user_context)
        
        # Assert
        self.assertFalse(result)
        # Verify that rejection message was sent
        user_context.message.reply_text.assert_called_once()

    @patch("jira_telegram_bot.adapters.services.telegram.authentication.LOGGER")
    @patch("jira_telegram_bot.adapters.services.telegram.authentication.TELEGRAM_SETTINGS")
    async def test_is_user_allowed_logs_unauthorized_access(self, mock_settings: MagicMock, mock_logger: MagicMock) -> None:
        """Test that unauthorized access is properly logged."""
        # Arrange
        mock_settings.ALLOWED_USERS = ["authorized_user"]
        user_context = self._create_mock_update(username="unauthorized_user", chat_type="private")
        
        # Act
        await self.auth_service.is_user_allowed(user_context)
        
        # Assert
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        self.assertIn("unauthorized_user", log_message.lower())
        self.assertIn("private", log_message.lower())

    @patch("jira_telegram_bot.adapters.services.telegram.authentication.TELEGRAM_SETTINGS")
    @patch("jira_telegram_bot.adapters.services.telegram.authentication.TelegramAuthentication")
    async def test_legacy_function_check_user_allowed(self, mock_auth_class: MagicMock, mock_settings: MagicMock) -> None:
        """Test that the legacy function correctly delegates to the class."""
        # Arrange
        mock_auth_instance = AsyncMock()
        mock_auth_class.return_value = mock_auth_instance
        mock_auth_instance.is_user_allowed.return_value = True
        update = self._create_mock_update(username="test_user")
        
        # Act
        result = await check_user_allowed(update)
        
        # Assert
        self.assertTrue(result)
        mock_auth_instance.is_user_allowed.assert_called_once_with(update)

    def _create_mock_update(self, username: str, chat_type: str = "private") -> Update:
        """Create a mock Update object for testing.
        
        Args:
            username: The username to use in the mock
            chat_type: The chat type to use in the mock
            
        Returns:
            A mock Update object configured with the given parameters
        """
        mock_user = MagicMock(spec=User)
        mock_user.username = username
        
        mock_chat = MagicMock(spec=Chat)
        mock_chat.type = chat_type
        
        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.chat = mock_chat
        mock_message.reply_text = AsyncMock()
        
        mock_update = MagicMock(spec=Update)
        mock_update.message = mock_message
        
        return mock_update


if __name__ == "__main__":
    unittest.main()