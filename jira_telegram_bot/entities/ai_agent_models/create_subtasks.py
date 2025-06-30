"""Input and output models for create subtasks use case."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List

from pydantic import BaseModel
from pydantic import Field


class CreateSubtasksInput(BaseModel):
    """Input model for creating subtasks."""
    
    project_context: str = Field(description="Context and information about the project")
    description: str = Field(description="Description of the work needed")
    departments: str = Field(description="List of available departments/components")
    department_details: str = Field(description="Detailed information about each department")
    assignee_details: str = Field(description="Information about team members and their roles")


class SubtaskItem(BaseModel):
    """Model for a single subtask."""
    
    summary: str = Field(description="Subtask summary")
    description: str = Field(description="Subtask description")
    story_points: float = Field(description="Estimated story points (0.5-8)")
    component: str = Field(description="Component/department responsible")
    assignee: str = Field(description="Suggested assignee")
    priority: str = Field(description="Task priority (High, Medium, Low)")
    acceptance_criteria: List[str] = Field(description="List of acceptance criteria")


class CreateSubtasksResult(BaseModel):
    """Result model for create subtasks use case."""
    
    subtasks: List[SubtaskItem] = Field(description="List of created subtasks")
    total_story_points: float = Field(description="Total estimated story points")
    components_involved: List[str] = Field(description="List of components/departments involved")
