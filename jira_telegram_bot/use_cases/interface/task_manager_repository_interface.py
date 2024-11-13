from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot.entities.task import TaskData


class TaskManagerRepositoryInterface(ABC):
    @abstractmethod
    def get_projects(self):
        pass

    @abstractmethod
    def get_project_components(self, project_key):
        pass

    @abstractmethod
    def get_epics(self, project_key: str):
        pass

    @abstractmethod
    def get_board_id(self, project_key: str) -> Optional[int]:
        pass

    @abstractmethod
    def get_sprints(self, board_id):
        pass

    @abstractmethod
    def get_project_versions(self, project_key):
        pass

    @abstractmethod
    def get_issue_types_for_project(self, project_key):
        pass

    @abstractmethod
    def get_priorities(self):
        pass

    @abstractmethod
    def get_assignees(self, project_key: str) -> List[str]:
        pass

    @abstractmethod
    def search_users(self, username: str) -> List[str]:
        pass

    @abstractmethod
    def build_issue_fields(self, task_data: TaskData) -> dict:
        pass

    @abstractmethod
    def handle_attachments(self, issue: Issue, attachments: Dict[str, List]):
        pass

    @abstractmethod
    def create_issue(self, fields):
        pass

    @abstractmethod
    def add_attachment(self, issue, attachment, filename):
        pass

    @abstractmethod
    def create_task(self, task_data: TaskData) -> Issue:
        pass
