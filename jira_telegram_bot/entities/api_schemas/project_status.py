"""API schema models for project status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatusCount(BaseModel):
    """Task status count model.
    
    Args:
        status: Task status name
        count: Number of tasks in this status
    """
    status: str = Field(description="Task status name")
    count: int = Field(description="Number of tasks in this status")


class ProjectSummary(BaseModel):
    """Project summary information.
    
    Args:
        key: Project key
        name: Project name
        task_count: Total number of tasks in the project
        status_counts: Count of tasks by status
        last_updated: Last updated timestamp
    """
    key: str = Field(description="Project key")
    name: str = Field(description="Project name")
    task_count: int = Field(description="Total number of tasks in the project")
    status_counts: List[TaskStatusCount] = Field(description="Count of tasks by status")
    last_updated: Optional[datetime] = Field(None, description="Last updated timestamp")


class ProjectListResponse(BaseModel):
    """Response model for project list endpoint.
    
    Args:
        projects: List of project summary information
    """
    projects: List[ProjectSummary] = Field(description="List of project summary information")


class ProjectDetailResponse(BaseModel):
    """Response model for project detail endpoint.
    
    Args:
        project: Project summary information
        sprint_data: Current sprint information
        upcoming_deadlines: Upcoming deadlines
    """
    project: ProjectSummary = Field(description="Project summary information")
    sprint_data: Optional[Dict] = Field(None, description="Current sprint information")
    upcoming_deadlines: Optional[List[Dict]] = Field(None, description="Upcoming deadlines")


class ProjectStatusUpdateRequest(BaseModel):
    """Request model for updating project status tracking.
    
    Args:
        track: Whether to track this project for status updates
        notification_channel: Optional Telegram channel ID for notifications
    """
    track: bool = Field(description="Whether to track this project for status updates")
    notification_channel: Optional[str] = Field(None, description="Telegram channel ID for notifications")


class ProjectStatusUpdateResponse(BaseModel):
    """Response model for updating project status tracking.
    
    Args:
        project_key: Project key
        tracking_enabled: Whether tracking is enabled
        notification_channel: Telegram channel ID for notifications
    """
    project_key: str = Field(description="Project key")
    tracking_enabled: bool = Field(description="Whether tracking is enabled")
    notification_channel: Optional[str] = Field(None, description="Telegram channel ID for notifications")
