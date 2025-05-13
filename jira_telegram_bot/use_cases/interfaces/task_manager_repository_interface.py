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

    @abstractmethod
    def add_comment(self, issue_key: str, comment: str):
        pass

    @abstractmethod
    def search_for_issues(self, query: str, max_results: int = 1000) -> List[Issue]:
        pass

    @abstractmethod
    def get_stories_by_epic(self, epic_key: str, project_key: str) -> List[Issue]:
        pass

    @abstractmethod
    def get_stories_by_project(
        self, 
        project_key: str,
        epic_link: str = None,
        status: str = None,
        filters: str = None,
    ) -> List[Issue]:
        pass

    @abstractmethod
    def get_labels(self, project_key: str) -> List[str]:
        pass

    @abstractmethod
    def set_labels(self, project_key: str, labels: List[str]) -> bool:
        pass

    @abstractmethod
    def transition_task(self, issue_key: str, status: str) -> None:
        pass

    @abstractmethod
    def assign_issue(self, issue_key: str, assignee: str) -> None:
        pass

    @abstractmethod
    def update_issue(self, issue_key: str, task_data: TaskData) -> None:
        pass

    @abstractmethod
    def update_issue_from_fields(self, issue_key: str, fields: dict) -> None:
        pass

    @abstractmethod
    def get_issue(self, issue_key: str) -> Optional[Issue]:
        pass

    @abstractmethod
    def build_task_data_from_issue(self, issue: Issue) -> TaskData:
        pass

    @abstractmethod
    def create_task_data_from_jira_issue(self, issue) -> TaskData:
        pass
