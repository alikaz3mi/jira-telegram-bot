"""Team evaluation repository interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationRow


class TeamEvaluationRepositoryInterface(ABC):
    """Interface for team evaluation data storage."""

    @abstractmethod
    async def save_evaluation(self, evaluation: TeamEvaluationRow) -> None:
        """Save a team evaluation row.
        
        Args:
            evaluation: Team evaluation data to save.
        """
        pass

    @abstractmethod
    async def save_evaluations_batch(self, evaluations: List[TeamEvaluationRow]) -> int:
        """Save multiple team evaluation rows in a batch.
        
        Args:
            evaluations: List of team evaluation data to save.
            
        Returns:
            Number of rows saved.
        """
        pass

    @abstractmethod
    async def get_sprint_evaluations(
        self,
        sprint_id: int,
        project: Optional[str] = None
    ) -> List[TeamEvaluationRow]:
        """Get all evaluations for a specific sprint.
        
        Args:
            sprint_id: Sprint ID.
            project: Optional project filter.
            
        Returns:
            List of evaluation rows for the sprint.
        """
        pass

    @abstractmethod
    async def get_developer_evaluations(
        self,
        developer_name: str,
        limit: Optional[int] = None
    ) -> List[TeamEvaluationRow]:
        """Get evaluation history for a specific developer.
        
        Args:
            developer_name: Developer name.
            limit: Optional limit on number of rows returned.
            
        Returns:
            List of evaluation rows for the developer.
        """
        pass

    @abstractmethod
    async def delete_sprint_evaluations(self, sprint_id: int) -> int:
        """Delete all evaluations for a sprint.
        
        Args:
            sprint_id: Sprint ID.
            
        Returns:
            Number of rows deleted.
        """
        pass

    @abstractmethod
    async def evaluation_exists(
        self,
        sprint_id: int,
        developer_name: str,
        department: str,
        project: str
    ) -> bool:
        """Check if an evaluation already exists.
        
        Args:
            sprint_id: Sprint ID.
            developer_name: Developer name.
            department: Department.
            project: Project.
            
        Returns:
            True if evaluation exists, False otherwise.
        """
        pass
