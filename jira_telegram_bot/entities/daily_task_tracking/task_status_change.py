"""Task status change entity."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StatusChangeType(str, Enum):
    """Type of status change."""

    REGRESSION = "regression"
    PROGRESSION = "progression"
    OTHER = "other"


class TaskStatusChange(BaseModel):
    """Entity representing a task status change."""

    issue_key: str = Field(description="Jira issue key")
    from_status: str = Field(description="Previous status")
    to_status: str = Field(description="New status")
    changed_by: str = Field(description="Who made the change")
    changed_at: datetime = Field(description="When change was made")
    change_type: StatusChangeType = Field(description="Type of change")
    assignee: Optional[str] = Field(
        None,
        description="Task assignee at time of change",
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for change (if provided)",
    )
    notified: bool = Field(
        default=False,
        description="Whether assignee was notified",
    )
