"""Data models for daily task status tracking."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class DelayReason(str, Enum):
    """Enumeration of possible delay reasons mapped to Jira values."""
    
    UNCLEAR_EXPLANATION = "unclear explanation"
    INCOMPLETE_DESIGN = "incomplete design"
    BLOCKING_ISSUE = "blocking issue"
    TECHNICAL_ISSUE = "technical issue"
    LACK_OF_KNOWLEDGE = "lack of knowledge"


class TaskStatusUpdate(BaseModel):
    """Model for a single task status update from user."""
    
    issue_key: str
    action: str
    time_spent_hours: Optional[float] = None
    work_description: Optional[str] = None
    delay_reason: Optional[DelayReason] = None
    delay_comment: Optional[str] = None


class SubtaskRequest(BaseModel):
    """Model for subtask creation request."""
    
    parent_issue_key: str
    summary: str
    description: Optional[str] = None
    requested_by: str
    project_key: str


class DailyStatusSession(BaseModel):
    """Model for tracking a user's daily status session."""
    
    telegram_user_id: int
    telegram_username: str
    jira_username: str
    tasks: List[str]
    current_task_index: int = 0
    updates: List[TaskStatusUpdate] = []
    is_complete: bool = False
