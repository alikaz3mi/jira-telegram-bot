"""Input and output models for progress report generation."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot.entities.jira.issue import JiraIssue


class GenerateProgressReportInput(BaseModel):
    """Input model for progress report generation."""
    
    assignee: str = Field(description="The team member name")
    sprint_label: str = Field(description="The sprint label")
    selected_issue_keys: List[str] = Field(description="List of selected issue keys")
    available_tasks: List[JiraIssue] = Field(description="Available tasks in the sprint")
    raw_transcript: str = Field(description="Raw input text from user")


class GenerateProgressReportResult(BaseModel):
    """Result model for progress report generation."""
    
    issue_key: str = Field(description="The JIRA issue key")
    progress: str = Field(description="Description of progress made")
    blockers: str = Field(description="Any blockers or issues encountered")
    time_spent: str = Field(description="Estimated time spent on the task")
