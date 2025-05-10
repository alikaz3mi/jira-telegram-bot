from __future__ import annotations

from typing import List, Optional

from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class CreateTaskUseCase:
    """
    Use case for creating a new Jira task.
    """

    def __init__(self, jira_repo: TaskManagerRepositoryInterface):
        self._jira_repo = jira_repo

    def run(
        self,
        project_key: str,
        summary: str,
        description: str,
        task_type: str = "Task",
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
    ):
        data = TaskData(
            project_key=project_key,
            summary=summary,
            description=description,
            task_type=task_type,
            labels=labels or [],
            assignee=assignee,
        )
        issue = self._jira_repo.create_task(data)
        return issue
