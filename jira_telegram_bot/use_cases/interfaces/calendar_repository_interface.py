"""Calendar repository interface for team evaluation."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, Set


class CalendarRepositoryInterface(ABC):
    """Interface for calendar data operations."""

    @abstractmethod
    async def get_holidays(self, year: int) -> Set[date]:
        """Get holidays for a given year.
        
        Args:
            year: The year to get holidays for
            
        Returns:
            Set of holiday dates
        """
        pass

    @abstractmethod
    async def get_disabled_days(self, year: int) -> Set[date]:
        """Get disabled/non-working days for a given year.
        
        Args:
            year: The year to get disabled days for
            
        Returns:
            Set of disabled dates
        """
        pass

    @abstractmethod
    async def get_calendar_header(self, year: int, month: int) -> Dict:
        """Get calendar header information for a specific month.
        
        Args:
            year: The year
            month: The month (1-12)
            
        Returns:
            Dictionary containing calendar metadata
        """
        pass
