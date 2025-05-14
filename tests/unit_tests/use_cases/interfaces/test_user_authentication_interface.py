"""Tests for UserAuthenticationInterface."""

import unittest
from typing import List
from unittest.mock import AsyncMock

from jira_telegram_bot.use_cases.interfaces.user_authentication_interface import (
    UserAuthenticationInterface,
)


class TestUserAuthenticationInterface(unittest.TestCase):
    """Test cases for the UserAuthenticationInterface."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.mock_interface = AsyncMock(spec=UserAuthenticationInterface)

    def test_interface_methods_exist(self) -> None:
        """Test that the interface defines the expected methods."""
        self.assertTrue(hasattr(UserAuthenticationInterface, "is_user_allowed"))
        self.assertTrue(hasattr(UserAuthenticationInterface, "get_allowed_users"))

    async def test_a_is_user_allowed_called(self) -> None:
        """Test is_user_allowed method is called with correct arguments."""
        username = "test_user"
        self.mock_interface.is_user_allowed.return_value = True
        
        result = await self.mock_interface.is_user_allowed(username)
        
        self.mock_interface.is_user_allowed.assert_called_once_with(username)
        self.assertTrue(result)

    async def test_a_get_allowed_users_called(self) -> None:
        """Test get_allowed_users method is called and returns expected value."""
        allowed_users = ["user1", "user2"]
        self.mock_interface.get_allowed_users.return_value = allowed_users
        
        result = await self.mock_interface.get_allowed_users()
        
        self.mock_interface.get_allowed_users.assert_called_once()
        self.assertEqual(result, allowed_users)


if __name__ == "__main__":
    unittest.main()