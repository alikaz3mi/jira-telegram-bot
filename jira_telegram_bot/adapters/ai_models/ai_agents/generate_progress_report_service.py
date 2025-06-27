from typing import List

from jira_telegram_bot.adapters.ai_models.ai_agents.prompts.prompt_template_loader import PromptTemplateLoader
from jira_telegram_bot.adapters.ai_models.providers.llm_provider_interface import LlmProviderInterface
from jira_telegram_bot.entities.jira.issue import JiraIssue
from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport


class GenerateProgressReportService:
    """Service for generating structured progress reports from raw input using AI."""

    def __init__(self, llm_provider: LlmProviderInterface):
        """Initialize the service with LLM provider.

        Args:
            llm_provider: The language model provider for processing.
        """
        self._llm_provider = llm_provider
        self._prompt_template = PromptTemplateLoader.load_template(
            "generate_progress_report"
        )

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
        task_summaries = self._format_task_summaries(available_tasks)
        selected_keys_str = ", ".join(selected_issue_keys) if selected_issue_keys else "None selected"

        chain = self._prompt_template.prompt | self._llm_provider | self._prompt_template.parser

        response = await chain.ainvoke({
            "assignee": assignee,
            "sprint_label": sprint_label,
            "selected_issue_keys": selected_keys_str,
            "task_summaries": task_summaries,
            "raw_transcript": raw_transcript,
        })

        return [
            ProgressReport(
                issue_key=report["issue_key"],
                progress=report["progress"],
                blockers=report["blockers"],
                time_spent=report["time_spent"],
            )
            for report in response["reports"]
        ]

    def _format_task_summaries(self, tasks: List[JiraIssue]) -> str:
        """Format task summaries for the prompt.

        Args:
            tasks: List of JIRA issues to format.

        Returns:
            Formatted string of task summaries.
        """
        if not tasks:
            return "No tasks available"

        summaries = []
        for task in tasks:
            summary = f"- {task.key}: {task.summary}"
            if task.assignee:
                summary += f" (Assigned: {task.assignee})"
            summaries.append(summary)

        return "\n".join(summaries)
