from typing import List

from jira_telegram_bot.adapters.repositories.file_storage.prompt_catalog import FilePromptCatalog
from jira_telegram_bot.entities.jira.issue import JiraIssue
from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol


class GenerateProgressReportService:
    """AI service for generating progress reports from user input."""

    def __init__(self, ai_service: AIServiceProtocol, prompt_catalog: FilePromptCatalog):
        """Initialize the service with dependencies.

        Args:
            ai_service: AI service for LLM calls.
            prompt_catalog: Catalog for loading prompt templates.
        """
        self._ai_service = ai_service
        self._prompt_catalog = prompt_catalog

    async def generate_progress_report(
        self,
        assignee: str,
        sprint_label: str,
        selected_issue_keys: List[str],
        available_tasks: List[JiraIssue],
        raw_transcript: str,
    ) -> List[ProgressReport]:
        """Generate structured progress reports from raw input.

        Args:
            assignee: The team member reporting progress.
            sprint_label: The current sprint label.
            selected_issue_keys: List of issue keys selected by the user.
            available_tasks: List of available tasks in the sprint.
            raw_transcript: Raw text or speech-to-text transcript.

        Returns:
            List of structured progress reports.

        Raises:
            Exception: If AI processing fails.
        """
        prompt = await self._prompt_catalog.get_prompt("generate_progress_report")
        
        # Format task summaries for the prompt
        task_summaries = self._format_task_summaries(available_tasks)
        
        # Prepare inputs for the AI prompt
        inputs = {
            "assignee": assignee,
            "sprint_label": sprint_label,
            "selected_issue_keys": ", ".join(selected_issue_keys) if selected_issue_keys else "None",
            "task_summaries": task_summaries,
            "raw_transcript": raw_transcript,
        }
        
        # Call AI service to generate structured output
        result = await self._ai_service.run(prompt, inputs)
        
        # Parse and convert to ProgressReport entities
        reports = []
        if "reports" in result:
            for report_data in result["reports"]:
                reports.append(
                    ProgressReport(
                        issue_key=report_data["issue_key"],
                        progress=report_data["progress"],
                        blockers=report_data["blockers"],
                        time_spent=report_data["time_spent"],
                    )
                )
        
        return reports

    def _format_task_summaries(self, available_tasks: List[JiraIssue]) -> str:
        """Format available tasks for the AI prompt.

        Args:
            available_tasks: List of available JIRA issues.

        Returns:
            Formatted string describing available tasks.
        """
        if not available_tasks:
            return "No tasks available in the current sprint."
        
        formatted_tasks = []
        for task in available_tasks:
            task_line = f"- {task.key}: {task.summary}"
            if task.assignee:
                task_line += f" (assigned to: {task.assignee})"
            if task.status:
                task_line += f" [status: {task.status}]"
            formatted_tasks.append(task_line)
        
        return "\n".join(formatted_tasks)
