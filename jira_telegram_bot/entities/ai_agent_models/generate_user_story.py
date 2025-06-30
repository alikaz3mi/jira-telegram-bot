"""Input and output models for user story generation."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class GenerateUserStoryInput(BaseModel):
    """Input model for user story generation."""
    
    raw_text: str = Field(description="Raw input text describing the requirement")
    project_key: str = Field(description="JIRA project key")
    project_context: Optional[str] = Field(
        default=None,
        description="Additional context about the project"
    )
    available_components: Optional[List[str]] = Field(
        default_factory=list,
        description="Available components in the project"
    )
    available_epics: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Available epics in the project"
    )
    current_sprint_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Information about the current sprint"
    )


class UserStoryCandidate(BaseModel):
    """Model for a generated user story candidate."""
    
    summary: str = Field(description="User story summary/title")
    description: str = Field(description="Detailed user story description")
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="List of acceptance criteria"
    )
    story_points: Optional[int] = Field(
        default=None,
        description="Estimated story points (1, 2, 3, 5, 8, 13, etc.)"
    )
    priority: Optional[str] = Field(
        default="Medium",
        description="Story priority (Low, Medium, High, Critical)"
    )
    components: Optional[List[str]] = Field(
        default_factory=list,
        description="Suggested components for the story"
    )
    labels: Optional[List[str]] = Field(
        default_factory=list,
        description="Suggested labels for the story"
    )
    epic_link: Optional[str] = Field(
        default=None,
        description="Link to parent epic if applicable"
    )
    assignee_suggestion: Optional[str] = Field(
        default=None,
        description="Suggested assignee based on components"
    )


class GenerateUserStoryResult(BaseModel):
    """Result model for user story generation."""
    
    user_story: UserStoryCandidate = Field(description="Generated user story")
    confidence_score: Optional[float] = Field(
        default=None,
        description="AI confidence score (0.0 to 1.0)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="AI reasoning for the generated story"
    )
    alternative_suggestions: Optional[List[UserStoryCandidate]] = Field(
        default_factory=list,
        description="Alternative user story candidates"
    )
    processing_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata from AI processing"
    )