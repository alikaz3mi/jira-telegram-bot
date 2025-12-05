"""Status change entity for tracking Jira issue status transitions."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class StatusChange(BaseModel):
    """Represents a status change in a Jira issue."""

    issue_key: str = Field(description="The Jira issue key")
    from_status: Optional[str] = Field(default=None, description="Previous status")
    to_status: str = Field(description="New status")
    changed_at: datetime = Field(description="When the status changed")
    changed_by: Optional[str] = Field(default=None, description="Who changed the status")
    project: str = Field(description="Project key")

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
