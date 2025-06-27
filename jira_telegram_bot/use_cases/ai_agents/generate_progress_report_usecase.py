from datetime import datetime
from typing import List, Optional
import uuid

from jira_telegram_bot.entities.ai_agent_models.generate_progress_report import GenerateProgressReportInput
from jira_telegram_bot.entities.ai_agent_models.generate_progress_report import GenerateProgressReportResult
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.entities.jira.issue import JiraIssue
from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase
from jira_telegram_bot.use_cases.interfaces.progress_report_repository_interface import ProgressReportRepositoryInterface


class GenerateProgressReportUseCase(BaseAIAgentUseCase):
    """Use case for generating and storing progress reports from user input."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
        repository: ProgressReportRepositoryInterface,
    ):
        """Initialize the use case with dependencies.

        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
            repository: Repository for storing progress reports.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.GENERATE_PROGRESS_REPORT
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

        # Prepare input data for AI processing
        input_data = GenerateProgressReportInput(
            assignee=assignee,
            sprint_label=sprint_label,
            selected_issue_keys=selected_issue_keys,
            available_tasks=available_tasks,
            raw_transcript=raw_transcript,
        )

        # Convert to dictionary for AI service
        ai_inputs = {
            "assignee": assignee,
            "sprint_label": sprint_label,
            "selected_issue_keys": selected_issue_keys,
            "task_summaries": [task.summary for task in available_tasks],
            "raw_transcript": raw_transcript,
        }

        # Process with AI service
        ai_response = await self._process_with_ai(ai_inputs)

        # Parse AI response into domain entities
        reports = []
        for report_data in ai_response.get("reports", []):
            reports.append(ProgressReport(
                issue_key=report_data["issue_key"],
                progress=report_data["progress"],
                blockers=report_data["blockers"],
                time_spent=report_data["time_spent"],
                assignee=assignee,
                reported_at=datetime.utcnow(),
                report_id=str(uuid.uuid4()),
            ))

        # Store reports
        stored_reports = await self._repository.save_reports(reports)
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
