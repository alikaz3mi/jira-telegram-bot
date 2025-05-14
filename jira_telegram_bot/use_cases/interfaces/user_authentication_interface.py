"""Interface for user authentication services."""

from abc import ABC, abstractmethod
from typing import List


class UserAuthenticationInterface(ABC):
    """Interface for user authentication services."""
    
    @abstractmethod
    async def is_user_allowed(self, username: str) -> bool:
        """Check if a user is allowed based on their username.
        
        Args:
            username: The username to check
            
        Returns:
            True if user is allowed, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_allowed_users(self) -> List[str]:
        """Get list of all allowed users.
        
        Returns:
            List of allowed usernames
        """
        pass