"""File storage implementation of user authentication repository."""

import json
import os
from pathlib import Path
from typing import List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.user_authentication_interface import (
    UserAuthenticationInterface,
)


class FileUserAuthenticationRepository(UserAuthenticationInterface):
    """File-based implementation of user authentication repository."""
    
    def __init__(self, auth_file_path: str):
        """Initialize the file-based user authentication repository.
        
        Args:
            auth_file_path: Path to the JSON file containing allowed users
        """
        self.auth_file_path = Path(auth_file_path)
        
    async def is_user_allowed(self, username: str) -> bool:
        """Check if a user is allowed based on their username.
        
        Args:
            username: The username to check
            
        Returns:
            True if user is allowed, False otherwise
        """
        allowed_users = await self.get_allowed_users()
        return username in allowed_users
    
    async def get_allowed_users(self) -> List[str]:
        """Get list of all allowed users from the file storage.
        
        Returns:
            List of allowed usernames
            
        Raises:
            FileNotFoundError: If the authentication file doesn't exist
            json.JSONDecodeError: If the authentication file isn't valid JSON
        """
        try:
            if not self.auth_file_path.exists():
                LOGGER.warning(f"Authentication file not found: {self.auth_file_path}")
                return []
                
            with open(self.auth_file_path, "r") as file:
                data = json.load(file)
                
            if not isinstance(data, dict) or "allowed_users" not in data:
                LOGGER.warning("Invalid authentication file format: missing 'allowed_users' key")
                return []
                
            allowed_users = data.get("allowed_users", [])
            if not isinstance(allowed_users, list):
                LOGGER.warning("Invalid authentication file format: 'allowed_users' is not a list")
                return []
                
            return allowed_users
            
        except json.JSONDecodeError:
            LOGGER.error(f"Failed to parse authentication file: {self.auth_file_path}")
            return []
        except Exception as e:
            LOGGER.error(f"Error reading authentication file: {str(e)}")
            return []