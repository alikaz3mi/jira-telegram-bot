"""Tests for FileUserAuthenticationRepository."""

import json
import os
import unittest
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, mock_open

from jira_telegram_bot.adapters.repositories.file_storage.user_authentication_repository import (
    FileUserAuthenticationRepository,
)


class TestFileUserAuthenticationRepository(IsolatedAsyncioTestCase):
    """Test cases for FileUserAuthenticationRepository."""

    def setUp(self) -> None:
        """Set up the test repository with a temporary file."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.auth_file_path = Path(self.temp_dir.name) / "allowed_users.json"

    def tearDown(self) -> None:
        """Clean up temporary directory after tests."""
        self.temp_dir.cleanup()

    async def test_a_is_user_allowed_returns_true(self) -> None:
        """Test is_user_allowed returns True for allowed users."""
        # Create test file with allowed users
        allowed_users = {"allowed_users": ["test_user", "admin_user"]}
        with open(self.auth_file_path, "w") as f:
            json.dump(allowed_users, f)
            
        # Create repository
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        # Test allowed user
        result = await repo.is_user_allowed("test_user")
        self.assertTrue(result)

    async def test_a_is_user_allowed_returns_false(self) -> None:
        """Test is_user_allowed returns False for unauthorized users."""
        # Create test file with allowed users
        allowed_users = {"allowed_users": ["test_user", "admin_user"]}
        with open(self.auth_file_path, "w") as f:
            json.dump(allowed_users, f)
            
        # Create repository
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        # Test unauthorized user
        result = await repo.is_user_allowed("unauthorized_user")
        self.assertFalse(result)

    async def test_a_get_allowed_users_success(self) -> None:
        """Test get_allowed_users returns the correct list."""
        expected_users = ["test_user", "admin_user"]
        allowed_users = {"allowed_users": expected_users}
        with open(self.auth_file_path, "w") as f:
            json.dump(allowed_users, f)
            
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        result = await repo.get_allowed_users()
        self.assertEqual(result, expected_users)

    async def test_a_get_allowed_users_file_not_found(self) -> None:
        """Test get_allowed_users returns empty list when file not found."""
        # Create repository with non-existent file
        non_existent_path = Path(self.temp_dir.name) / "non_existent.json"
        repo = FileUserAuthenticationRepository(str(non_existent_path))
        
        result = await repo.get_allowed_users()
        self.assertEqual(result, [])

    async def test_a_get_allowed_users_invalid_json(self) -> None:
        """Test get_allowed_users returns empty list for invalid JSON."""
        # Create invalid JSON file
        with open(self.auth_file_path, "w") as f:
            f.write("{ invalid json")
            
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        result = await repo.get_allowed_users()
        self.assertEqual(result, [])

    async def test_a_get_allowed_users_missing_key(self) -> None:
        """Test get_allowed_users returns empty list when allowed_users key is missing."""
        # Create JSON file without allowed_users key
        with open(self.auth_file_path, "w") as f:
            json.dump({"other_key": "value"}, f)
            
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        result = await repo.get_allowed_users()
        self.assertEqual(result, [])

    async def test_a_get_allowed_users_invalid_format(self) -> None:
        """Test get_allowed_users returns empty list when allowed_users is not a list."""
        # Create JSON file with wrong format for allowed_users
        with open(self.auth_file_path, "w") as f:
            json.dump({"allowed_users": "not_a_list"}, f)
            
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        result = await repo.get_allowed_users()
        self.assertEqual(result, [])

    @patch('jira_telegram_bot.adapters.repositories.file_storage.user_authentication_repository.open', 
           side_effect=Exception("Unexpected error"))
    async def test_a_get_allowed_users_unexpected_error(self, mock_open) -> None:
        """Test get_allowed_users returns empty list when unexpected error occurs."""
        repo = FileUserAuthenticationRepository(str(self.auth_file_path))
        
        result = await repo.get_allowed_users()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()