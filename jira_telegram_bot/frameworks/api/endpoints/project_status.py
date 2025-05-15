"""Project status API endpoint."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas.project_status import (
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectStatusUpdateRequest,
    ProjectStatusUpdateResponse,
)
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint
from jira_telegram_bot.use_cases.project_status.get_project_status_use_case import GetProjectStatusUseCase
from jira_telegram_bot.use_cases.project_status.update_project_tracking_use_case import UpdateProjectTrackingUseCase


class ProjectStatusEndpoint(ServiceAPIEndpointBluePrint):
    """API endpoint for project status operations."""
    
    def __init__(
        self,
        get_project_status_use_case: GetProjectStatusUseCase,
        update_project_tracking_use_case: UpdateProjectTrackingUseCase
    ):
        """Initialize the endpoint.
        
        Args:
            get_project_status_use_case: Use case for retrieving project status
            update_project_tracking_use_case: Use case for updating project tracking settings
        """
        self.get_project_status_use_case = get_project_status_use_case
        self.update_project_tracking_use_case = update_project_tracking_use_case
    
    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for project status operations.
        
        Returns:
            Configured APIRouter for project status endpoints
        """
        api_route = APIRouter(
            prefix="/projects",
            tags=["Projects"]
        )
        
        @api_route.get(
            "/",
            summary="Get list of projects with status summary",
            description="Returns a list of all projects with their status summaries",
            response_model=ProjectListResponse
        )
        async def get_projects(
            limit: Optional[int] = Query(None, description="Maximum number of projects to return"),
            status: Optional[str] = Query(None, description="Filter projects by status")
        ):
            """Get list of projects with status summary.
            
            Args:
                limit: Maximum number of projects to return
                status: Filter projects by status
                
            Returns:
                List of project summaries
            """
            try:
                LOGGER.debug(f"Getting project list with limit={limit}, status={status}")
                projects = await self.get_project_status_use_case.get_project_list(limit=limit, status=status)
                return ProjectListResponse(projects=projects)
            except Exception as e:
                LOGGER.error(f"Error getting project list: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error retrieving projects: {str(e)}"
                )
        
        @api_route.get(
            "/{project_key}",
            summary="Get detailed project status",
            description="Returns detailed status information for a specific project",
            response_model=ProjectDetailResponse
        )
        async def get_project_detail(project_key: str):
            """Get detailed project status.
            
            Args:
                project_key: Project key
                
            Returns:
                Detailed project status
            """
            try:
                LOGGER.debug(f"Getting project details for {project_key}")
                project_detail = await self.get_project_status_use_case.get_project_detail(project_key)
                
                if not project_detail:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Project '{project_key}' not found"
                    )
                
                return project_detail
            except HTTPException:
                raise
            except Exception as e:
                LOGGER.error(f"Error getting project detail: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error retrieving project details: {str(e)}"
                )
        
        @api_route.put(
            "/{project_key}/tracking",
            summary="Update project status tracking",
            description="Enable or disable status tracking for a project",
            response_model=ProjectStatusUpdateResponse
        )
        async def update_project_tracking(
            project_key: str,
            update_data: ProjectStatusUpdateRequest
        ):
            """Update project status tracking.
            
            Args:
                project_key: Project key
                update_data: Update request data
                
            Returns:
                Updated tracking status
            """
            try:
                LOGGER.debug(f"Updating tracking for {project_key}: {update_data}")
                result = await self.update_project_tracking_use_case.update_tracking(
                    project_key=project_key,
                    track=update_data.track,
                    notification_channel=update_data.notification_channel
                )
                
                return ProjectStatusUpdateResponse(
                    project_key=project_key,
                    tracking_enabled=result.get("tracking_enabled", False),
                    notification_channel=result.get("notification_channel")
                )
            except Exception as e:
                LOGGER.error(f"Error updating project tracking: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error updating project tracking: {str(e)}"
                )
        
        return api_route
