from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class DeadlineAlert(BaseModel):
    """Entity representing a deadline alert for a Jira issue."""

    issue_key: str = Field(description="Jira issue key")
    summary: str = Field(description="Issue summary")
    assignee: Optional[str] = Field(default=None, description="Issue assignee")
    reporter: Optional[str] = Field(default=None, description="Issue reporter")
    due_date: Optional[datetime] = Field(default=None, description="Issue due date")
    target_end: Optional[datetime] = Field(
        default=None,
        description="Target end date from custom field",
    )
    days_remaining: int = Field(description="Number of days until deadline")
    project_key: str = Field(description="Jira project key")
    status: str = Field(description="Current issue status")
    priority: Optional[str] = Field(default=None, description="Issue priority")
    issue_url: str = Field(description="Direct URL to the issue")
    issue_type: Optional[str] = Field(
        default=None,
        description="Issue type (Story, Task, Sub-task, etc.)",
    )
    sprint_info: Optional[str] = Field(
        default=None,
        description="Sprint information if in active sprint",
    )

    @property
    def effective_deadline(self) -> Optional[datetime]:
        """Return the effective deadline (due_date takes precedence over target_end)."""
        return self.due_date or self.target_end

    @property
    def is_overdue(self) -> bool:
        """Check if the issue is overdue."""
        return self.days_remaining < 0

    @property
    def is_story_or_task(self) -> bool:
        """Check if the issue is a Story or Task (not a subtask)."""
        if not self.issue_type:
            return True  # Default to True if type is unknown
        return self.issue_type.lower() in ["story", "task", "bug", "epic"]

    @property
    def is_in_active_sprint(self) -> bool:
        """Check if the issue is in an active sprint."""
        return bool(self.sprint_info)

    @property
    def is_in_review(self) -> bool:
        """Check if the issue is in review status."""
        if not self.status:
            return False
        status_lower = self.status.lower()
        return "review" in status_lower or "بررسی" in status_lower

    @property
    def urgency_level(self) -> str:
        """Determine urgency level based on days remaining."""
        if self.days_remaining < 0:
            return "overdue"
        elif self.days_remaining == 0:
            return "today"
        elif self.days_remaining <= 1:
            return "urgent"
        elif self.days_remaining <= 3:
            return "high"
        elif self.days_remaining <= 7:
            return "medium"
        else:
            return "low"
