from abc import ABC, abstractmethod
from typing import List, Optional

from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport


class ProgressReportRepositoryInterface(ABC):
    """Interface for progress report repository operations."""

    @abstractmethod
    async def save_reports(self, reports: List[ProgressReport]) -> List[ProgressReport]:
        """Save multiple progress reports.

        Args:
            reports: List of progress reports to save.

        Returns:
            List of saved progress reports with any updated fields.

        Raises:
            Exception: If saving fails.
        """
        pass

    @abstractmethod
    async def save_report(self, report: ProgressReport) -> ProgressReport:
        """Save a single progress report.

        Args:
            report: Progress report to save.

        Returns:
            Saved progress report with any updated fields.

        Raises:
            Exception: If saving fails.
        """
        pass

    @abstractmethod
    async def get_reports_by_assignee_and_sprint(
        self,
        assignee: str,
        sprint_label: str,
        limit: Optional[int] = None,
    ) -> List[ProgressReport]:
        """Retrieve progress reports by assignee and sprint.

        Args:
            assignee: The team member name.
            sprint_label: The sprint label.
            limit: Maximum number of reports to return.

        Returns:
            List of matching progress reports.

        Raises:
            Exception: If retrieval fails.
        """
        pass

    @abstractmethod
    async def get_report_by_id(self, report_id: str) -> Optional[ProgressReport]:
        """Retrieve a progress report by its ID.

        Args:
            report_id: Unique identifier for the report.

        Returns:
            Progress report if found, None otherwise.

        Raises:
            Exception: If retrieval fails.
        """
        pass

    @abstractmethod
    async def get_reports_by_date_range(
        self,
        start_date: str,
        end_date: str,
        assignee: Optional[str] = None,
    ) -> List[ProgressReport]:
        """Retrieve progress reports within a date range.

        Args:
            start_date: Start date in ISO format.
            end_date: End date in ISO format.
            assignee: Optional team member filter.

        Returns:
            List of matching progress reports.

        Raises:
            Exception: If retrieval fails.
        """
        pass
