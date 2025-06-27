"""Input and output models for story decomposition."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List

from pydantic import BaseModel
from pydantic import Field


class StoryDecompositionInput(BaseModel):
    """Input model for story decomposition."""
    
    project_context: str = Field(description="Context and information about the project")
    description: str = Field(description="Description of the work needed")
    departments: str = Field(description="List of available departments/components")
    department_details: str = Field(description="Detailed information about each department")
    assignee_details: str = Field(description="Information about team members and their roles")


class ComponentTask(BaseModel):
    """Model for component-specific tasks."""
    
    component: str = Field(description="Component/department name")
    subtasks: List[Dict[str, Any]] = Field(description="List of subtasks for this component")


class StoryItem(BaseModel):
    """Model for a decomposed story."""
    
    summary: str = Field(description="Story summary")
    description: str = Field(description="Story description")
    story_points: int = Field(description="Estimated story points")
    priority: str = Field(description="Story priority")
    component_tasks: List[ComponentTask] = Field(description="Component-specific tasks")


class StoryDecompositionResult(BaseModel):
    """Result model for story decomposition."""
    
    stories: List[StoryItem] = Field(description="List of decomposed stories with their tasks")
