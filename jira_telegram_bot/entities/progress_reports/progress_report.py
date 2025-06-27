from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProgressReport(BaseModel):
    """Entity representing a daily progress report for a specific task.
    
    Args:
        issue_key: The JIRA issue key (e.g., 'PROJ-123').
        progress: Description of progress made on the task.
        blockers: Any obstacles or issues encountered.
        time_spent: Estimated time spent on the task.
        assignee: Team member who reported the progress.
        reported_at: Timestamp when the report was created.
        report_id: Unique identifier for the report.
    """
    
    issue_key: str = Field(description="The JIRA issue key")
    progress: str = Field(description="Description of progress made")
    blockers: str = Field(description="Any blockers or issues encountered")
    time_spent: str = Field(description="Estimated time spent on the task")
    assignee: Optional[str] = Field(None, description="Team member who reported the progress")
    reported_at: Optional[datetime] = Field(None, description="Timestamp when the report was created")
    report_id: Optional[str] = Field(None, description="Unique identifier for the report")

    class Config:
        """Pydantic model configuration."""
        
        frozen = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
