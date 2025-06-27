import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport
from jira_telegram_bot.use_cases.interfaces.progress_report_repository_interface import ProgressReportRepositoryInterface


class FileProgressReportRepository(ProgressReportRepositoryInterface):
    """File-based implementation of progress report repository."""

    def __init__(self, storage_path: str = "data/storage/progress_reports.json"):
        """Initialize the repository with storage path.

        Args:
            storage_path: Path to the JSON file for storing progress reports.
        """
        self._storage_path = Path(storage_path)
        self._ensure_storage_directory()

    async def save_reports(self, reports: List[ProgressReport]) -> List[ProgressReport]:
        """Save multiple progress reports.

        Args:
            reports: List of progress reports to save.

        Returns:
            List of saved progress reports.

        Raises:
            Exception: If saving fails.
        """
        existing_reports = await self._load_reports()
        
        for report in reports:
            existing_reports.append(report.dict())
        
        await self._save_reports_to_file(existing_reports)
        return reports

    async def save_report(self, report: ProgressReport) -> ProgressReport:
        """Save a single progress report.

        Args:
            report: Progress report to save.

        Returns:
            Saved progress report.

        Raises:
            Exception: If saving fails.
        """
        reports = await self.save_reports([report])
        return reports[0]

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
        """
        all_reports = await self._load_reports()
        
        matching_reports = [
            ProgressReport(**report_data)
            for report_data in all_reports
            if report_data.get("assignee") == assignee
        ]
        
        # Sort by reported_at descending (most recent first)
        matching_reports.sort(
            key=lambda r: r.reported_at or datetime.min,
            reverse=True
        )
        
        if limit:
            matching_reports = matching_reports[:limit]
        
        return matching_reports

    async def get_report_by_id(self, report_id: str) -> Optional[ProgressReport]:
        """Retrieve a progress report by its ID.

        Args:
            report_id: Unique identifier for the report.

        Returns:
            Progress report if found, None otherwise.
        """
        all_reports = await self._load_reports()
        
        for report_data in all_reports:
            if report_data.get("report_id") == report_id:
                return ProgressReport(**report_data)
        
        return None

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
        """
        all_reports = await self._load_reports()
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        matching_reports = []
        for report_data in all_reports:
            if not report_data.get("reported_at"):
                continue
                
            reported_at = datetime.fromisoformat(
                report_data["reported_at"].replace('Z', '+00:00')
            )
            
            if start_dt <= reported_at <= end_dt:
                if not assignee or report_data.get("assignee") == assignee:
                    matching_reports.append(ProgressReport(**report_data))
        
        return matching_reports

    def _ensure_storage_directory(self) -> None:
        """Ensure the storage directory exists."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

    async def _load_reports(self) -> List[dict]:
        """Load all reports from the JSON file.

        Returns:
            List of report dictionaries.
        """
        if not self._storage_path.exists():
            return []
        
        try:
            with open(self._storage_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (json.JSONDecodeError, IOError):
            return []

    async def _save_reports_to_file(self, reports: List[dict]) -> None:
        """Save reports to the JSON file.

        Args:
            reports: List of report dictionaries to save.

        Raises:
            Exception: If saving fails.
        """
        with open(self._storage_path, 'w', encoding='utf-8') as file:
            json.dump(reports, file, indent=2, default=str)
