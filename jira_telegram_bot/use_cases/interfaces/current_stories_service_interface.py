from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from io import BytesIO

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport


class CurrentStoriesServiceInterface(ABC):
    """Interface for current stories service operations.
    
    This interface defines the contract for services that handle
    current stories operations including XLSX generation.
    """
    
    @abstractmethod
    async def generate_stories_xlsx(
        self, 
        report: CurrentStoriesReport
    ) -> BytesIO:
        """Generate XLSX file from current stories report.
        
        Args:
            report: The current stories report data
            
        Returns:
            BytesIO containing the XLSX file
        """
        pass
    
    @abstractmethod
    def create_assignee_abbreviation(self, assignee_name: str) -> str:
        """Create abbreviation from assignee name.
        
        Args:
            assignee_name: Full assignee name (e.g., 'a_kazemi')
            
        Returns:
            Abbreviated name (e.g., 'AK')
        """
        pass
