from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Optional
from typing import Any

from jira_telegram_bot.entities.task import TaskData, JiraIssueReference


class TaskManagerRepositoryInterface(ABC):
    @abstractmethod
    def get_projects(self) -> List[Any]:
        """Get list of available projects.
        
        Returns:
            List of project objects
        """
        pass

    @abstractmethod
    def get_project_components(self, project_key: str) -> List[Any]:
        """Get components for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of component objects
        """
        pass

    @abstractmethod
    def get_epics(self, project_key: str) -> List[Any]:
        """Get epics for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of epic objects
        """
        pass

    @abstractmethod
    def get_board_id(self, project_key: str) -> Optional[int]:
        """Get board ID for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            Board ID if exists, None otherwise
        """
        pass

    @abstractmethod
    def get_sprints(self, board_id: int) -> List[Any]:
        """Get sprints for a board.
        
        Args:
            board_id: Board identifier
            
        Returns:
            List of sprint objects
        """
        pass

    @abstractmethod
    def get_project_versions(self, project_key: str) -> List[Any]:
        """Get versions for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of version objects
        """
        pass

    @abstractmethod
    def get_issue_types_for_project(self, project_key: str) -> List[Any]:
        """Get issue types for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of issue type objects
        """
        pass

    @abstractmethod
    def get_priorities(self) -> List[Any]:
        """Get available priorities.
        
        Returns:
            List of priority objects
        """
        pass

    @abstractmethod
    def get_assignees(self, project_key: str) -> List[str]:
        """Get available assignees for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of assignee usernames
        """
        pass

    @abstractmethod
    def search_users(self, username: str) -> List[str]:
        """Search for users by username.
        
        Args:
            username: Search term
            
        Returns:
            List of matching usernames
        """
        pass

    @abstractmethod
    def build_issue_fields(self, task_data: TaskData) -> dict:
        """Build issue fields dictionary from task data.
        
        Args:
            task_data: Task data entity
            
        Returns:
            Dictionary of issue fields
        """
        pass

    @abstractmethod
    def create_task(self, task_data: TaskData) -> JiraIssueReference:
        """Create a new task from task data.
        
        Args:
            task_data: Task data entity
            
        Returns:
            Created issue reference
        """
        pass

    @abstractmethod
    def get_stories_by_project(self, project_key: str) -> List[JiraIssueReference]:
        """Get stories for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of story issue references
        """
        pass

    @abstractmethod
    def get_stories_by_epic(self, epic_key: str) -> List[JiraIssueReference]:
        """Get stories for an epic.
        
        Args:
            epic_key: Epic identifier
            
        Returns:
            List of story issue references
        """
        pass

    @abstractmethod
    def add_comment(self, issue_key: str, comment: str) -> None:
        """Add a comment to an issue.
        
        Args:
            issue_key: Issue identifier
            comment: Comment text
        """
        pass

    @abstractmethod
    def assign_issue(self, issue_key: str, assignee: str) -> None:
        """Assign an issue to a user.
        
        Args:
            issue_key: Issue identifier
            assignee: Username to assign to
        """
        pass

    @abstractmethod
    def update_issue(self, issue_key: str, task_data: TaskData) -> None:
        """Update an issue with task data.
        
        Args:
            issue_key: Issue identifier
            task_data: Task data entity with updated fields
        """
        pass

    @abstractmethod
    def update_issue_from_fields(self, issue_key: str, fields: dict) -> None:
        """Update an issue with raw fields.
        
        Args:
            issue_key: Issue identifier
            fields: Dictionary of fields to update
        """
        pass

    @abstractmethod
    def get_issue(self, issue_key: str) -> Optional[JiraIssueReference]:
        """Get an issue by key.
        
        Args:
            issue_key: Issue identifier
            
        Returns:
            Issue reference if exists, None otherwise
        """
        pass

    @abstractmethod
    def create_task_data_from_jira_issue(self, issue: Any) -> TaskData:
        """Convert a Jira issue to TaskData entity.
        
        Args:
            issue: Jira issue object
            
        Returns:
            TaskData entity
        """
        pass
