"""Release entity for Jira releases/versions."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class Release(BaseModel):
    """Jira release/version entity."""

    id: str = Field(description="Release ID")
    name: str = Field(description="Release name")
    description: Optional[str] = Field(default=None, description="Release description")
    released: bool = Field(
        default=False,
        description="Whether the release is marked as released",
    )
    archived: bool = Field(default=False, description="Whether the release is archived")
    releaseDate: Optional[str] = Field(
        default=None,
        description="Release date (YYYY-MM-DD)",
    )
    project: str = Field(description="Project key")

    class Config:
        """Pydantic configuration."""

        frozen = True
