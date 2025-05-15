"""Use case for retrieving project status information."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas.project_status import (
    ProjectDetailResponse,
    ProjectSummary,
    TaskStatusCount,
)
from jira_telegram_bot.use_cases.interfaces.project_status_interface import ProjectStatusInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface


class GetProjectStatusUseCase(ProjectStatusInterface):
    """Use case for retrieving project status information."""
    
    def __init__(self, task_manager_repository: TaskManagerRepositoryInterface):
        """Initialize the use case.
        
        Args:
            task_manager_repository: Repository for task management operations
        """
        self.task_manager_repository = task_manager_repository
    
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
        try:
            # Get projects from task manager
            projects = await self.task_manager_repository.get_projects()
            
            # Filter by status if provided
            if status:
                projects = [p for p in projects if p.get("projectStatus", "").lower() == status.lower()]
            
            # Apply limit
            if limit and limit > 0:
                projects = projects[:limit]
            
            # Transform to project summaries
            project_summaries = []
            for project in projects:
                project_key = project.get("key")
                
                # Get status counts for each project
                status_data = await self.task_manager_repository.get_issues_by_status(
                    project_key=project_key
                )
                
                status_counts = []
                total_count = 0
                for status_name, count in status_data.items():
                    status_counts.append(TaskStatusCount(status=status_name, count=count))
                    total_count += count
                
                project_summaries.append(
                    ProjectSummary(
                        key=project_key,
                        name=project.get("name", ""),
                        task_count=total_count,
                        status_counts=status_counts,
                        last_updated=datetime.now()
                    )
                )
            
            return project_summaries
            
        except Exception as e:
            LOGGER.error(f"Error getting project list: {str(e)}", exc_info=True)
            raise
    
    async def get_project_detail(self, project_key: str) -> Optional[ProjectDetailResponse]:
        """Get detailed project status.
        
        Args:
            project_key: Project key
            
        Returns:
            Detailed project status or None if not found
        """
        try:
            # Check if project exists
            project = await self.task_manager_repository.get_project(project_key)
            if not project:
                return None
            
            # Get status counts
            status_data = await self.task_manager_repository.get_issues_by_status(
                project_key=project_key
            )
            
            status_counts = []
            total_count = 0
            for status_name, count in status_data.items():
                status_counts.append(TaskStatusCount(status=status_name, count=count))
                total_count += count
            
            # Get current sprint data
            sprint_data = await self.task_manager_repository.get_active_sprint(project_key)
            
            # Get upcoming deadlines
            upcoming_deadlines = await self.task_manager_repository.get_upcoming_deadlines(
                project_key=project_key,
                days=14
            )
            
            # Create project summary
            project_summary = ProjectSummary(
                key=project_key,
                name=project.get("name", ""),
                task_count=total_count,
                status_counts=status_counts,
                last_updated=datetime.now()
            )
            
            return ProjectDetailResponse(
                project=project_summary,
                sprint_data=sprint_data,
                upcoming_deadlines=upcoming_deadlines
            )
            
        except Exception as e:
            LOGGER.error(f"Error getting project detail: {str(e)}", exc_info=True)
            raise
