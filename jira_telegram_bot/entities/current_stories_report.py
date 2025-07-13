from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CurrentStoryItem(BaseModel):
    """Domain model for a single story item in the current stories report.
    
    Args:
        issue_number: Issue key/number
        issue_name: Story/issue name
        story_status: Status of the story itself
        remaining_hours: Remaining work estimate in hours (numeric only)
        priority: Priority level
        assignees_abbr: Abbreviated assignee names from subtasks
        release: Release version
        label_feature: Label/Feature with colored badge
        epic_name: Epic name (not ID)
        creation_date_jalali: Issue creation date in Jalali calendar
        real_start_date_jalali: First task moved to in-progress (Jalali)
        complete_date_jalali: Date when moved to done (Jalali)
        weeks_passed: Weeks passed since creation date
    """
    issue_number: str = Field(description="Issue key/number")
    issue_name: str = Field(description="Story/issue name")
    story_status: Optional[str] = Field(default=None, description="Status of the story itself")
    remaining_hours: Optional[float] = Field(default=None, description="Remaining work estimate in hours")
    priority: Optional[str] = Field(default=None, description="Priority level")
    assignees_abbr: List[str] = Field(default_factory=list, description="Abbreviated assignee names")
    release: Optional[str] = Field(default=None, description="Release version")
    label_feature: Optional[str] = Field(default=None, description="Label or feature name")
    epic_name: Optional[str] = Field(default=None, description="Epic name")
    creation_date_jalali: Optional[str] = Field(default=None, description="Issue creation date in Jalali calendar")
    real_start_date_jalali: Optional[str] = Field(default=None, description="First task moved to in-progress (Jalali)")
    complete_date_jalali: Optional[str] = Field(default=None, description="Date when moved to done (Jalali)")
    weeks_passed: Optional[float] = Field(default=None, description="Weeks passed since creation date")


class CurrentStoriesReport(BaseModel):
    """Domain model for the current stories report.
    
    Args:
        project_key: Jira project key
        sprint_name: Sprint name
        stories: List of story items
    """
    project_key: str = Field(description="Jira project key")
    sprint_name: str = Field(description="Sprint name")
    stories: List[CurrentStoryItem] = Field(default_factory=list, description="List of story items")
