from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport


class CurrentStoriesServiceInterface(ABC):
    """Interface for current stories service operations.
    
    This interface defines the contract for services that handle
    current stories business logic and Google Sheets integration.
    """
    
    @abstractmethod
    def create_assignee_abbreviation(self, assignee_name: str) -> str:
        """Create abbreviation from assignee name.
        
        Args:
            assignee_name: Full assignee name (e.g., 'a_kazemi')
            
        Returns:
            Abbreviated name (e.g., 'AK')
        """
        pass
    
    @abstractmethod
    async def save_to_google_sheets(
        self, 
        report: CurrentStoriesReport, 
        sprint_name: str,
        jira_base_url: str
    ) -> bool:
        """Save current stories report to Google Sheets.
        
        Args:
            report: The current stories report data
            sprint_name: Name of the sprint (used as worksheet name)
            jira_base_url: Base URL for creating JIRA issue links
            
        Returns:
            True if successful, False otherwise
        """
        pass
