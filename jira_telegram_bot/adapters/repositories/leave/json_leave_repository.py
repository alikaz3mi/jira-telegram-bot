"""JSON-based leave repository implementation (stub)."""

from datetime import date
from typing import Dict, Set

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import LeaveRepositoryInterface


class JsonLeaveRepository(LeaveRepositoryInterface):
    """JSON file-based leave repository (stub implementation)."""

    def __init__(self, data_path: str = "data/storage"):
        """Initialize the repository.
        
        Args:
            data_path: Path to the directory containing leave JSON files
        """
        self.data_path = data_path
        LOGGER.info("JsonLeaveRepository initialized as stub - returns empty leave data")

    async def get_user_leaves(self, username: str, year: int) -> Set[date]:
        """Get leave dates for a specific user in a given year.
        
        Args:
            username: The username to get leaves for
            year: The year to get leaves for
            
        Returns:
            Empty set (stub implementation)
        """
        LOGGER.debug(f"Stub: get_user_leaves called for {username}, {year} - returning empty set")
        return set()

    async def get_all_leaves(self, year: int) -> Dict[str, Set[date]]:
        """Get all leave dates for all users in a given year.
        
        Args:
            year: The year to get leaves for
            
        Returns:
            Empty dictionary (stub implementation)
        """
        LOGGER.debug(f"Stub: get_all_leaves called for {year} - returning empty dict")
        return {}
