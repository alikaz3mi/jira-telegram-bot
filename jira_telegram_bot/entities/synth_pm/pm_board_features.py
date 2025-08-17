from __future__ import annotations

from datetime import datetime
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class SynthPMFeatureEntity(BaseModel):
    """Entity representing a SynthPM feature from Google Sheets."""
    # FIXME: departments should be a list, not a string

    row_number: int = Field(description="Row number in the sheet")
    task_title: str = Field(description="Task title/وظیفه")
    epic: Optional[str] = Field(default=None, description="Epic")
    release: Optional[str] = Field(default=None, description="Release/ریلیز")
    necessity: Optional[str] = Field(default=None, description="Necessity/ضرورت")
    priority: Optional[str] = Field(default=None, description="Priority/اولویت")
    status: Optional[str] = Field(default=None, description="Status/وضعیت")
    eta_hours: Optional[int] = Field(default=None, description="ETA hours")
    total_hours: Optional[int] = Field(default=None, description="Total hours")
    departments: Optional[str] = Field(default=None, description="Departments")
    involved_people: Optional[str] = Field(default=None, description="Involved people/افراد درگیر")
    ai: Optional[str] = Field(default=None, description="AI")
    backend: Optional[str] = Field(default=None, description="Backend")
    frontend: Optional[str] = Field(default=None, description="Front-end")
    devops: Optional[str] = Field(default=None, description="DevOPS")
    ui_ux: Optional[str] = Field(default=None, description="UI/UX")
    creation_date: Optional[datetime] = Field(default=None, description="Creation date/تاریخ ایجاد")
    implementation_start_date: Optional[datetime] = Field(default=None, description="Implementation start date/تاریخ شروع پیاده سازی")
    deadline: Optional[datetime] = Field(default=None, description="Deadline/ددلاین")
    sprint: Optional[str] = Field(default=None, description="Sprint/اسپرینت")
    last_sprint: Optional[str] = Field(default=None, description="Last sprint/آخرین اسپرینت")
    sprint_list: Optional[List[str]] = Field(default=None, description="List of sprints/لیست اسپرینت ها")
    dependencies: Optional[str] = Field(default=None, description="Dependencies/وابستگی ها")
    initial_delivery_time: Optional[datetime] = Field(default=None, description="Initial delivery time/زمان تحویل اولیه")
    description: Optional[str] = Field(default=None, description="Description/توضیحات")
    jira_issue_key: Optional[str] = Field(default=None, description="Associated PM Board Jira issue key")
    developer_board_issue_key: Optional[str] = Field(default=None, description="Associated developer's board Jira issue key")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class SynthPMSheetSyncStatus(BaseModel):
    """Entity representing sync status for SynthPM sheet."""

    sheet_id: str = Field(description="Google Sheet ID")
    worksheet_name: str = Field(description="Worksheet name")
    last_sync_time: datetime = Field(description="Last synchronization time")
    total_rows_synced: int = Field(description="Total rows synchronized")
    errors: List[str] = Field(default_factory=list, description="Sync errors")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
