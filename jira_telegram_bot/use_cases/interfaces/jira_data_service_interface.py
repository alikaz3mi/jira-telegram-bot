"""Service interface for fetching Jira data."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import List

from jira_telegram_bot.entities.jira_report import JiraIssueDetail


class JiraDataServiceInterface(ABC):
    """Interface for fetching data from Jira."""

    @abstractmethod
    async def fetch_project_issues(self, project_key: str) -> List[JiraIssueDetail]:
        """Fetch all issues for a project with comprehensive details.
        
        Args:
            project_key: The Jira project key.
            
        Returns:
            List of detailed issue information including worklogs and links.
        """

    @abstractmethod
    async def fetch_issue_details(self, issue_key: str) -> JiraIssueDetail:
        """Fetch detailed information for a specific issue.
        
        Args:
            issue_key: The Jira issue key.
            
        Returns:
            Detailed issue information.
        """
