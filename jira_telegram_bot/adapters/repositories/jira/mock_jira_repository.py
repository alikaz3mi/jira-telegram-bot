"""Mock Jira repository for development and testing purposes."""

from __future__ import annotations

from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.entities.task import Task


class MockJiraRepository(TaskManagerRepositoryInterface):
    """Mock implementation of the Jira repository for testing without a real Jira instance."""
    
    def __init__(self):
        """Initialize the mock repository."""
        LOGGER.info("Initializing Mock Jira Repository for development/testing")
        self._tasks = {}
    
    async def create_task(self, summary: str, description: str, project_key: str, 
                         issue_type: str, **kwargs) -> str:
        """Create a task in Jira.
        
        Args:
            summary: Task summary/title
            description: Task detailed description
            project_key: Jira project key
            issue_type: Type of issue (e.g., "Story", "Task")
            **kwargs: Additional fields for the task
            
        Returns:
            Task key (e.g., "PROJ-123")
        """
        task_id = f"{project_key}-{len(self._tasks) + 1}"
        self._tasks[task_id] = {
            "key": task_id,
            "summary": summary,
            "description": description,
            "project_key": project_key,
            "issue_type": issue_type,
            "status": "To Do",
            "created": datetime.now().isoformat(),
            **kwargs
        }
        LOGGER.info(f"Mock created task {task_id}")
        return task_id
    
    async def get_task(self, task_key: str) -> Task:
        """Get task details.
        
        Args:
            task_key: Jira task key
            
        Returns:
            Task object with details
        """
        if task_key in self._tasks:
            task_data = self._tasks[task_key]
            return Task(
                key=task_data["key"],
                summary=task_data["summary"],
                status=task_data["status"],
                assignee=task_data.get("assignee", "Unassigned"),
                description=task_data.get("description", ""),
                due_date=task_data.get("due_date"),
                priority=task_data.get("priority", "Medium"),
                labels=task_data.get("labels", []),
            )
        LOGGER.warning(f"Mock task {task_key} not found")
        return Task(
            key=task_key,
            summary="Not Found",
            status="Unknown",
            assignee="Unassigned",
            description="Task not found in mock repository",
        )
    
    async def transition_task(self, task_key: str, transition_name: str) -> bool:
        """Transition a task to a new status.
        
        Args:
            task_key: Jira task key
            transition_name: Name of the transition to execute
            
        Returns:
            True if successful, False otherwise
        """
        if task_key in self._tasks:
            self._tasks[task_key]["status"] = transition_name
            LOGGER.info(f"Mock transitioned task {task_key} to {transition_name}")
            return True
        LOGGER.warning(f"Mock task {task_key} not found for transition")
        return False
    
    async def add_comment(self, task_key: str, comment: str) -> bool:
        """Add a comment to a task.
        
        Args:
            task_key: Jira task key
            comment: Comment text
            
        Returns:
            True if successful, False otherwise
        """
        if task_key in self._tasks:
            comments = self._tasks[task_key].get("comments", [])
            comments.append({
                "text": comment,
                "created": datetime.now().isoformat(),
            })
            self._tasks[task_key]["comments"] = comments
            LOGGER.info(f"Mock added comment to task {task_key}")
            return True
        LOGGER.warning(f"Mock task {task_key} not found for adding comment")
        return False
    
    async def assign_task(self, task_key: str, assignee: str) -> bool:
        """Assign a task to a user.
        
        Args:
            task_key: Jira task key
            assignee: Username to assign to
            
        Returns:
            True if successful, False otherwise
        """
        if task_key in self._tasks:
            self._tasks[task_key]["assignee"] = assignee
            LOGGER.info(f"Mock assigned task {task_key} to {assignee}")
            return True
        LOGGER.warning(f"Mock task {task_key} not found for assignment")
        return False
