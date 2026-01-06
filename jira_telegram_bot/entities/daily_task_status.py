"""Data models for daily task status tracking."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class DelayReason(str, Enum):
    """Enumeration of possible delay reasons."""
    
    DEPENDENCY = "dependency"
    UNCLEAR_REQUIREMENTS = "unclear_requirements"
    TECHNICAL_ISSUES = "technical_issues"
    OTHER_PRIORITIES = "other_priorities"
    PERSONAL = "personal"
    BLOCKED = "blocked"
    WAITING_REVIEW = "waiting_review"
    OTHER = "other"


class TaskStatusUpdate(BaseModel):
    """Model for a single task status update from user."""
    
    issue_key: str
    action: str
    time_spent_hours: Optional[float] = None
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
