from datetime import datetime
from typing import List, Optional
import uuid

from jira_telegram_bot.adapters.ai_models.ai_agents.generate_progress_report_service import GenerateProgressReportService
from jira_telegram_bot.entities.jira.issue import JiraIssue
from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport
from jira_telegram_bot.use_cases.interfaces.progress_report_repository_interface import ProgressReportRepositoryInterface


class GenerateProgressReportUseCase:
    """Use case for generating and storing progress reports from user input."""

    def __init__(
        self,
        ai_service: GenerateProgressReportService,
        repository: ProgressReportRepositoryInterface,
    ):
        """Initialize the use case with dependencies.

        Args:
            ai_service: Service for AI-powered report generation.
            repository: Repository for storing progress reports.
        """
        self._ai_service = ai_service
        self._repository = repository

    async def execute(
        self,
        assignee: str,
        sprint_label: str,
        selected_issue_keys: List[str],
        available_tasks: List[JiraIssue],
        raw_transcript: str,
    ) -> List[ProgressReport]:
        """Generate and store progress reports from raw input.

        Args:
            assignee: The team member reporting progress.
            sprint_label: The current sprint label.
            selected_issue_keys: List of issue keys selected by the user.
            available_tasks: List of available tasks in the sprint.
            raw_transcript: Raw text or speech-to-text transcript.

        Returns:
            List of generated and stored progress reports.

        Raises:
            ValueError: If input data is invalid.
            Exception: If AI processing or storage fails.
        """
        self._validate_input(assignee, sprint_label, raw_transcript)

        reports = await self._ai_service.generate_progress_report(
            assignee=assignee,
            sprint_label=sprint_label,
            selected_issue_keys=selected_issue_keys,
            available_tasks=available_tasks,
            raw_transcript=raw_transcript,
        )

        enriched_reports = self._enrich_reports(reports, assignee)
        stored_reports = await self._repository.save_reports(enriched_reports)

        return stored_reports

    def _validate_input(self, assignee: str, sprint_label: str, raw_transcript: str) -> None:
        """Validate input parameters.

        Args:
            assignee: The team member name.
            sprint_label: The sprint label.
            raw_transcript: The raw input text.

        Raises:
            ValueError: If any required parameter is empty or invalid.
        """
        if not assignee or not assignee.strip():
            raise ValueError("Assignee cannot be empty")
        
        if not sprint_label or not sprint_label.strip():
            raise ValueError("Sprint label cannot be empty")
        
        if not raw_transcript or not raw_transcript.strip():
            raise ValueError("Raw transcript cannot be empty")

    def _enrich_reports(self, reports: List[ProgressReport], assignee: str) -> List[ProgressReport]:
        """Enrich reports with additional metadata.

        Args:
            reports: List of generated reports.
            assignee: The team member name.

        Returns:
            List of enriched progress reports.
        """
        current_time = datetime.utcnow()
        
        return [
            ProgressReport(
                issue_key=report.issue_key,
                progress=report.progress,
                blockers=report.blockers,
                time_spent=report.time_spent,
                assignee=assignee,
                reported_at=current_time,
                report_id=str(uuid.uuid4()),
            )
            for report in reports
        ]

    async def get_reports_by_assignee_and_sprint(
        self,
        assignee: str,
        sprint_label: str,
        limit: Optional[int] = None,
    ) -> List[ProgressReport]:
        """Retrieve progress reports for a specific assignee and sprint.

        Args:
            assignee: The team member name.
            sprint_label: The sprint label.
            limit: Maximum number of reports to return.

        Returns:
            List of progress reports.
        """
        return await self._repository.get_reports_by_assignee_and_sprint(
            assignee=assignee,
            sprint_label=sprint_label,
            limit=limit,
        )
