"""Leave repository interface for team evaluation."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, Set


class LeaveRepositoryInterface(ABC):
    """Interface for leave data operations."""

    @abstractmethod
    async def get_user_leaves(self, username: str, year: int) -> Set[date]:
        """Get leave dates for a specific user in a given year.
        
        Args:
            username: The username to get leaves for
            year: The year to get leaves for
            
        Returns:
            Set of leave dates for the user
        """
        pass

    @abstractmethod
    async def get_all_leaves(self, year: int) -> Dict[str, Set[date]]:
        """Get all leave dates for all users in a given year.
        
        Args:
            year: The year to get leaves for
            
        Returns:
            Dictionary mapping usernames to their leave dates
        """
        pass
