from __future__ import annotations

from abc import ABC
from abc import abstractmethod


class TaskManagerRepositoryInterface(ABC):
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_projects(self):
        pass

    @abstractmethod
    def get_project_components(self, project_key):
        pass

    @abstractmethod
    def get_epics(self, project_key):
        pass

    @abstractmethod
    def get_boards(self):
        pass

    @abstractmethod
    def get_sprints(self, board_id):
        pass

    @abstractmethod
    def get_project_versions(self, project_key):
        pass

    @abstractmethod
    def create_issue(self, fields):
        pass

    @abstractmethod
    def add_attachment(self, issue, attachment, filename):
        pass
