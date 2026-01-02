"""Worklog entry entity."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorklogEntry(BaseModel):
    """Entity representing a worklog entry."""

    worklog_id: Optional[str] = Field(
        None,
        description="Jira worklog ID (if synced to Jira)",
    )
    issue_key: str = Field(description="Jira issue key")
    author: str = Field(description="Author username")
    time_spent_hours: float = Field(description="Time spent in hours")
    started_at: datetime = Field(
        default_factory=datetime.now,
        description="When work was performed",
    )
    comment: Optional[str] = Field(
        None,
        description="Worklog comment",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When worklog was created",
    )
    source: str = Field(
        default="daily_task_tracker",
        description="Source of worklog entry",
    )
