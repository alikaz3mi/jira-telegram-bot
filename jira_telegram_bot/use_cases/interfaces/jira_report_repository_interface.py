"""Repository interface for Jira reporting data."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import List, Optional

from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.entities.sync_status import SyncStatus


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

    @abstractmethod
    async def get_sync_status(self, project_key: str) -> Optional[SyncStatus]:
        """Retrieve sync status for a project.
        
        Args:
            project_key: The Jira project key.
            
        Returns:
            Sync status if exists, None otherwise.
        """

    @abstractmethod
    async def update_sync_status(self, sync_status: SyncStatus) -> None:
        """Update sync status for a project.
        
        Args:
            sync_status: Updated sync status to store.
        """
