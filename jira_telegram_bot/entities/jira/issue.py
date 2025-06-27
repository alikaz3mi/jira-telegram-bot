from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JiraIssue(BaseModel):
    """Entity representing a JIRA issue for the daily report system.
    
    Args:
        key: The JIRA issue key (e.g., 'PROJ-123').
        summary: Brief description of the issue.
        description: Detailed description of the issue.
        assignee: Username of the person assigned to the issue.
        status: Current status of the issue.
        issue_type: Type of the issue (Task, Bug, Story, etc.).
        project_key: Key of the project this issue belongs to.
        priority: Priority level of the issue.
        created: Date when the issue was created.
        updated: Date when the issue was last updated.
        due_date: Due date for the issue completion.
        story_points: Story points assigned to the issue.
        sprint_name: Name of the sprint this issue belongs to.
        epic_link: Key of the epic this issue is linked to.
        labels: List of labels attached to the issue.
        components: List of components this issue affects.
    """
    
    key: str = Field(description="JIRA issue key")
    summary: str = Field(description="Brief description of the issue")
    description: Optional[str] = Field(None, description="Detailed description of the issue")
    assignee: Optional[str] = Field(None, description="Username of the person assigned to the issue")
    status: Optional[str] = Field(None, description="Current status of the issue")
    issue_type: Optional[str] = Field(None, description="Type of the issue")
    project_key: Optional[str] = Field(None, description="Key of the project this issue belongs to")
    priority: Optional[str] = Field(None, description="Priority level of the issue")
    created: Optional[datetime] = Field(None, description="Date when the issue was created")
    updated: Optional[datetime] = Field(None, description="Date when the issue was last updated")
    due_date: Optional[datetime] = Field(None, description="Due date for the issue completion")
    story_points: Optional[float] = Field(None, description="Story points assigned to the issue")
    sprint_name: Optional[str] = Field(None, description="Name of the sprint this issue belongs to")
    epic_link: Optional[str] = Field(None, description="Key of the epic this issue is linked to")
    labels: Optional[list[str]] = Field(None, description="List of labels attached to the issue")
    components: Optional[list[str]] = Field(None, description="List of components this issue affects")

    class Config:
        """Pydantic model configuration."""
        
        frozen = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
