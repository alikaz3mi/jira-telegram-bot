"""Use case for answering a member's question about their own tasks."""
from __future__ import annotations

from typing import Sequence

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AIServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)

_PROMPT_TASK = "answer_task_question"


class AnswerTaskQuestionUseCase:
    """Answer questions about the asker's own tasks, read-only.

    Scoped deliberately: the model sees only the tasks assigned to the person
    asking, and can only produce text. Nothing here writes to Jira, so a wrong
    answer costs a correction rather than a bad edit.
    """

    def __init__(
        self,
        ai_service: AIServiceProtocol,
        prompt_catalog: PromptCatalogProtocol,
    ):
        """Initialize the use case.

        Args:
            ai_service: Service that runs the structured LLM call
            prompt_catalog: Catalog the answering prompt is loaded from
        """
        self.ai_service = ai_service
        self.prompt_catalog = prompt_catalog

    async def execute(
        self,
        question: str,
        tasks: Sequence[DailyTaskCheck],
    ) -> str:
        """Answer a question against the user's own tasks.

        Args:
            question: What the user asked
            tasks: The user's open issues

        Returns:
            The answer text, or an empty string if it could not be produced.
        """
        try:
            prompt = await self.prompt_catalog.get_prompt(_PROMPT_TASK)
            result = await self.ai_service.run(
                prompt,
                {"content": question, "tasks": self._format_tasks(tasks)},
                cleanse_llm_text=True,
            )
            return str(result.get("answer", "")).strip()
        except Exception as exc:
            LOGGER.error(f"Failed to answer task question: {exc}", exc_info=True)
            return ""

    @staticmethod
    def _format_tasks(tasks: Sequence[DailyTaskCheck]) -> str:
        """Render the tasks as the only context the answer may draw on."""
        if not tasks:
            return "(no open tasks)"

        lines = []
        for task in tasks:
            parts = [f"{task.issue_key}: {task.summary}"]
            parts.append(f"status={task.status}")
            parts.append(f"project={task.project_key}")
            if task.issue_type:
                parts.append(f"type={task.issue_type}")
            if task.sprint_name:
                parts.append(f"sprint={task.sprint_name}")
            if task.target_start:
                parts.append(f"start={task.target_start:%Y-%m-%d}")
            if task.target_end:
                parts.append(f"due={task.target_end:%Y-%m-%d}")
            if task.dependencies:
                parts.append(f"blocked_by={','.join(task.dependencies)}")
            if task.worklog_hours:
                parts.append(f"logged={task.worklog_hours}h")
            lines.append(" | ".join(parts))
        return "\n".join(lines)
