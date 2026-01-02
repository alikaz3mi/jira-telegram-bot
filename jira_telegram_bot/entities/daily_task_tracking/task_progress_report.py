"""User task progress report entity."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    DelayReason,
)


class UserTaskProgressReport(BaseModel):
    """Entity representing a user's task progress report."""

    report_id: str = Field(description="Unique report ID")
    issue_key: str = Field(description="Jira issue key")
    user_jira_username: str = Field(description="User's Jira username")
    user_telegram_username: Optional[str] = Field(
        None,
        description="User's Telegram username",
    )
    report_date: datetime = Field(
        default_factory=datetime.now,
        description="Date of report",
    )
    delay_reason: Optional[DelayReason] = Field(
        None,
        description="Reason for delay if task not started",
    )
    delay_reason_text: Optional[str] = Field(
        None,
        description="Custom delay reason text",
    )
    hours_spent: Optional[float] = Field(
        None,
        description="Hours spent on task",
    )
    worklog_added: bool = Field(
        default=False,
        description="Whether worklog was added to Jira",
    )
    subtask_requested: bool = Field(
        default=False,
        description="Whether user requested subtask creation",
    )
    po_notified: bool = Field(
        default=False,
        description="Whether PO was notified",
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes",
    )
