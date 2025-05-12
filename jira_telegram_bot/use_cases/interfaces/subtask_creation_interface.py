from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Protocol


class SubtaskCreationInterface(Protocol):
    """Interface for creating subtasks from a parent story."""

    async def create_subtasks(
        self,
        project_context: str,
        description: str,
        departments: str,
        department_details: str,
        assignee_details: str,
    ) -> Dict[str, Any]:
        """
        Create subtasks based on a parent story description.
        
        Args:
            project_context: Context and information about the project
            description: Description of the work needed
            departments: List of available departments/components
            department_details: Detailed information about each department
            assignee_details: Information about team members and their roles
            
        Returns:
            Dictionary containing the created subtasks
        """
        ...
