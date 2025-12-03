"""Jira report entities for Clean Architecture compliance."""
from __future__ import annotations

from datetime import datetime
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class WorklogEntry(BaseModel):
    """Represents a single worklog entry on a Jira issue."""

    id: str = Field(description="Worklog entry ID")
    author: str = Field(description="Author display name")
    time_spent: str = Field(description="Time spent in Jira format (e.g., '2h 30m')")
    time_spent_seconds: Optional[int] = Field(default=None, description="Time spent in seconds")
    created: datetime = Field(description="When the worklog was created")
    updated: datetime = Field(description="When the worklog was last updated")
    started: datetime = Field(description="When the work was started")
    comment: Optional[str] = Field(default=None, description="Worklog comment")

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LinkedIssue(BaseModel):
    """Represents a linked issue in Jira."""

    key: str = Field(description="Issue key")
    summary: str = Field(description="Issue summary")
    status: str = Field(description="Issue status")
    issue_type: str = Field(description="Issue type")
    relationship: str = Field(description="Link relationship (e.g., 'blocks', 'is blocked by')")


class JiraIssueDetail(BaseModel):
    """Comprehensive Jira issue details for reporting."""

    key: str = Field(description="Issue key")
    summary: str = Field(description="Issue summary")
    description: Optional[str] = Field(default=None, description="Issue description")
    epic_name: Optional[str] = Field(default=None, description="Epic name if applicable")
    comments: str = Field(default="", description="Concatenated comments")
    task_type: str = Field(description="Issue type")
    assignee: Optional[str] = Field(default=None, description="Assignee display name")
    reporter: str = Field(description="Reporter display name")
    priority: Optional[str] = Field(default=None, description="Priority name")
    status: str = Field(description="Status name")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    resolved_at: Optional[datetime] = Field(default=None, description="Resolution timestamp")
    target_start: Optional[datetime] = Field(default=None, description="Target start date")
    target_end: Optional[datetime] = Field(default=None, description="Target end date")
    due_date: Optional[datetime] = Field(default=None, description="Due date")
    project: Optional[str] = Field(default=None, description="Project key")
    story_points: Optional[float] = Field(default=None, description="Story points")
    components: List[str] = Field(default_factory=list, description="Component names")
    labels: List[str] = Field(default_factory=list, description="Labels")
    last_sprint: str = Field(default="Backlog", description="Last sprint name")
    sprint_repeats: int = Field(default=0, description="Number of sprints")
    release: List[str] = Field(default_factory=list, description="Fix versions")
    original_estimate: Optional[str] = Field(default=None, description="Original time estimate")
    remaining_estimate: Optional[str] = Field(default=None, description="Remaining time estimate")
    root_cause: Optional[str] = Field(default=None, description="Root cause for bugs")
    worklog_entries: List[WorklogEntry] = Field(default_factory=list, description="Worklog entries")
    linked_issues: List[LinkedIssue] = Field(default_factory=list, description="Linked issues")

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProjectReport(BaseModel):
    """Aggregated project report data."""

    project_key: str = Field(description="Project key")
    generated_at: datetime = Field(description="Report generation timestamp")
    total_issues: int = Field(description="Total number of issues")
    issues: List[JiraIssueDetail] = Field(description="List of all issues")

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
