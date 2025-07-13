from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CurrentStoryItem(BaseModel):
    """Domain model for a single story item in the current stories report.
    
    Args:
        story_number: Sequential number for the story
        issue_name: Story/issue name
        epic_name: Epic name (not ID)
        label_feature: Label/Feature with colored badge
        assignees_abbr: Abbreviated assignee names from subtasks
        remaining_hours: Remaining work estimate in hours
        release: Release version
        priority: Priority level
        progress: Progress indicator
        story_status: Status of the story itself
        review_tasks_count: Number of tasks in review status
        done_tasks_count: Number of tasks in done status
        other_tasks_count: Number of tasks in other statuses
    """
    story_number: int = Field(description="Sequential story number")
    issue_name: str = Field(description="Story/issue name")
    epic_name: Optional[str] = Field(default=None, description="Epic name")
    label_feature: Optional[str] = Field(default=None, description="Label or feature name")
    assignees_abbr: List[str] = Field(default_factory=list, description="Abbreviated assignee names")
    remaining_hours: Optional[float] = Field(default=None, description="Remaining work estimate in hours")
    release: Optional[str] = Field(default=None, description="Release version")
    priority: Optional[str] = Field(default=None, description="Priority level")
    progress: Optional[str] = Field(default=None, description="Progress indicator")
    story_status: Optional[str] = Field(default=None, description="Status of the story itself")
    review_tasks_count: int = Field(default=0, description="Number of tasks in review status")
    done_tasks_count: int = Field(default=0, description="Number of tasks in done status")
    other_tasks_count: int = Field(default=0, description="Number of tasks in other statuses")


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
