"""Use case for validating worklog existence."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class ValidateWorklogUseCase:
    """Use case for validating if a task has worklog entries."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
    ):
        """Initialize the use case.

        Args:
            task_manager_repository: Repository for task management
        """
        self.task_manager_repository = task_manager_repository

    async def execute(self, issue_key: str) -> bool:
        """Check if an issue has worklog entries.

        Args:
            issue_key: Jira issue key

        Returns:
            True if worklog exists, False otherwise
        """
        try:
            worklogs = self.task_manager_repository.jira.worklogs(issue_key)
            
            if not worklogs:
                return False
            
            total_seconds = sum(
                getattr(wl, "timeSpentSeconds", 0) for wl in worklogs
            )
            
            return total_seconds > 0
            
        except Exception as e:
            LOGGER.error(f"Error validating worklog for {issue_key}: {e}")
            return False
