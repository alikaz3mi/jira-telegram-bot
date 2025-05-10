"""Interface for authentication services."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuthenticationInterface(ABC):
    """Interface for authentication services."""

    @abstractmethod
    async def is_user_allowed(self, user_context: Any) -> bool:
        """Check if a user is allowed to perform actions.
        
        Args:
            user_context: User context information (such as Telegram's Update object)
                          or any context object containing user identification
        
        Returns:
            True if user is authorized, False otherwise
        """
        pass