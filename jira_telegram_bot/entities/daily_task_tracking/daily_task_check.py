"""Daily task check entity."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)


class DailyTaskCheck(BaseModel):
    """Entity representing a daily task check."""

    issue_key: str = Field(description="Jira issue key")
    summary: str = Field(description="Task summary")
    status: str = Field(description="Current Jira status")
    assignee: str = Field(description="Task assignee username")
    check_status: TaskCheckStatus = Field(description="Check status")
    check_date: datetime = Field(
        default_factory=datetime.now,
        description="Date of check",
    )
    target_start: Optional[datetime] = Field(
        None,
        description="Target start date",
    )
    target_end: Optional[datetime] = Field(
        None,
        description="Target end date",
    )
    sprint_name: Optional[str] = Field(
        None,
        description="Active sprint name",
    )
    project_key: str = Field(description="Project key")
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of dependency issue keys",
    )
    dependencies_completed: bool = Field(
        default=True,
        description="Whether all dependencies are completed",
    )
    worklog_hours: float = Field(
        default=0.0,
        description="Total hours logged",
    )
    parent_key: Optional[str] = Field(
        None,
        description=(
            "The Story or Task this Sub-task belongs to. A list of "
            "sub-tasks alone is unreadable; the parent is what a person "
            "recognises."
        ),
    )
    issue_type: Optional[str] = Field(
        None,
        description="Issue type (Task, Story, Bug, etc.)",
    )
    priority: Optional[str] = Field(
        None,
        description="Task priority",
    )
    description: Optional[str] = Field(
        None,
        description="Task description",
    )
