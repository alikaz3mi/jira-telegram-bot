"""Repository interface for Jira reporting data."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import List

from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import ProjectReport


class JiraReportRepositoryInterface(ABC):
    """Interface for Jira report data persistence."""

    @abstractmethod
    async def store_issues(self, issues: List[JiraIssueDetail]) -> None:
        """Store or update issues in the database.
        
        Args:
            issues: List of Jira issue details to store.
        """

    @abstractmethod
    async def get_project_report(self, project_key: str) -> ProjectReport:
        """Retrieve a project report.
        
        Args:
            project_key: The Jira project key.
            
        Returns:
            Complete project report with all issues.
        """

    @abstractmethod
    async def get_issues_by_keys(self, issue_keys: List[str]) -> List[JiraIssueDetail]:
        """Retrieve specific issues by their keys.
        
        Args:
            issue_keys: List of issue keys to retrieve.
            
        Returns:
            List of matching issue details.
        """
