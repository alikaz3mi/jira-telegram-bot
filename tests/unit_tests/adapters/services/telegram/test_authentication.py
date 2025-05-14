"""Tests for TelegramAuthenticationService."""

import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from jira_telegram_bot.adapters.services.telegram.authentication import (
    TelegramAuthenticationService,
)
from jira_telegram_bot.use_cases.interfaces.user_authentication_interface import (
    UserAuthenticationInterface,
)


class TestTelegramAuthenticationService(IsolatedAsyncioTestCase):
    """Test cases for TelegramAuthenticationService."""

    def setUp(self) -> None:
        """Set up test dependencies and mocks."""
        self.user_auth_repository = AsyncMock(spec=UserAuthenticationInterface)
        self.auth_service = TelegramAuthenticationService(
            user_authentication_repository=self.user_auth_repository
        )
        
        # Mock telegram update
        self.mock_user = MagicMock(spec=User)
        self.mock_chat = MagicMock(spec=Chat)
        self.mock_message = MagicMock(spec=Message)
        self.mock_update = MagicMock(spec=Update)
        
        # Configure mocks
        self.mock_update.message = self.mock_message
        self.mock_message.from_user = self.mock_user
        self.mock_message.chat = self.mock_chat
        
    async def test_a_check_user_allowed_authorized(self) -> None:
        """Test that authorized users pass the check."""
        # Set up mock
        self.mock_user.username = "test_user"
        self.mock_chat.type = "private"
        self.user_auth_repository.is_user_allowed.return_value = True
        
        # Execute test
        result = await self.auth_service.check_user_allowed(self.mock_update)
        
        # Verify results
        self.user_auth_repository.is_user_allowed.assert_called_once_with("test_user")
        self.assertTrue(result)
        self.mock_message.reply_text.assert_not_called()
        
    async def test_a_check_user_allowed_unauthorized(self) -> None:
        """Test that unauthorized users are rejected with a message."""
        # Set up mock
        self.mock_user.username = "unauthorized_user"
        self.mock_chat.type = "private"
        self.user_auth_repository.is_user_allowed.return_value = False
        
        # Execute test
        result = await self.auth_service.check_user_allowed(self.mock_update)
        
        # Verify results
        self.user_auth_repository.is_user_allowed.assert_called_once_with("unauthorized_user")
        self.assertFalse(result)
        self.mock_message.reply_text.assert_called_once()
        # Verify the message contains the username
        self.assertIn("unauthorized_user", self.mock_message.reply_text.call_args[0][0])
        self.assertIn("not authorized", self.mock_message.reply_text.call_args[0][0].lower())
    
    @patch("jira_telegram_bot.adapters.services.telegram.authentication.LOGGER")
    async def test_a_check_user_allowed_logging(self, mock_logger) -> None:
        """Test that unauthorized access is logged."""
        # Set up mock
        self.mock_user.username = "unauthorized_user"
        self.mock_chat.type = "group"
        self.user_auth_repository.is_user_allowed.return_value = False
        
        # Execute test
        await self.auth_service.check_user_allowed(self.mock_update)
        
        # Verify logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        self.assertIn("unauthorized_user", log_message)
        self.assertIn("group", log_message)


if __name__ == "__main__":
    unittest.main()