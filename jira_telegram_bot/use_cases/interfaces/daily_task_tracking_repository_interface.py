"""Interface for daily task tracking repository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from jira_telegram_bot.entities.daily_task_tracking.task_progress_report import (
    UserTaskProgressReport,
)


class DailyTaskTrackingRepositoryInterface(ABC):
    """Interface for daily task tracking data persistence."""

    @abstractmethod
    async def save_progress_report(
        self,
        report: UserTaskProgressReport,
    ) -> None:
        """Save a user task progress report.

        Args:
            report: Progress report to save
        """
        pass

    @abstractmethod
    async def get_progress_reports_by_user(
        self,
        user_jira_username: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[UserTaskProgressReport]:
        """Get progress reports for a user within a date range.

        Args:
            user_jira_username: User's Jira username
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of progress reports
        """
        pass

    @abstractmethod
    async def get_progress_reports_by_issue(
        self,
        issue_key: str,
    ) -> List[UserTaskProgressReport]:
        """Get all progress reports for an issue.

        Args:
            issue_key: Jira issue key

        Returns:
            List of progress reports
        """
        pass

    @abstractmethod
    async def get_last_report_for_issue(
        self,
        issue_key: str,
        user_jira_username: str,
    ) -> Optional[UserTaskProgressReport]:
        """Get the most recent progress report for an issue and user.

        Args:
            issue_key: Jira issue key
            user_jira_username: User's Jira username

        Returns:
            Most recent progress report or None
        """
        pass
