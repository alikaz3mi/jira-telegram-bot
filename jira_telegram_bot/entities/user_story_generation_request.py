"""Input entity for the main user story generation use case."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class UserStoryGenerationRequest(BaseModel):
    """Input entity for user story generation request."""
    
    raw_text: str = Field(description="Raw text describing the requirement")
    project: str = Field(description="Project key")
    product_area: Optional[str] = Field(
        default=None,
        description="Product or feature area context"
    )
    business_goal: Optional[str] = Field(
        default=None,
        description="Business goal or OKR context"
    )
    primary_persona: Optional[str] = Field(
        default=None,
        description="Primary persona for the story"
    )
    dependencies: Optional[str] = Field(
        default=None,
        description="Dependencies or constraints"
    )
    epic_context: Optional[str] = Field(
        default=None,
        description="Epic-level context"
    )
    parent_story_context: Optional[str] = Field(
        default=None,
        description="Parent story context"
    )
