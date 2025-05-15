"""Interface for project status use case."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from jira_telegram_bot.entities.api_schemas.project_status import ProjectDetailResponse, ProjectSummary


class ProjectStatusInterface(ABC):
    """Interface for retrieving project status information."""
    
    @abstractmethod
    async def get_project_list(
        self, 
        limit: Optional[int] = None, 
        status: Optional[str] = None
    ) -> List[ProjectSummary]:
        """Get a list of projects with status summary.
        
        Args:
            limit: Maximum number of projects to return
            status: Filter projects by status
            
        Returns:
            List of project summaries
        """
        pass
    
    @abstractmethod
    async def get_project_detail(self, project_key: str) -> Optional[ProjectDetailResponse]:
        """Get detailed project status.
        
        Args:
            project_key: Project key
            
        Returns:
            Detailed project status or None if not found
        """
        pass
