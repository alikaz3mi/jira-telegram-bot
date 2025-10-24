"""Entity representing a row in the story synchronization Google Sheet."""
from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class StorySheetRow(BaseModel):
    """Entity representing a row in the story Google Sheet.

    Column order matches the Google Sheet structure:
    ردیف، وظیفه، Epic، ضرورت، ریلیز، Departments، وضعیت، اولویت، Department Deps،
    ریلیز اصلی، ETA(h)، Total (h)، Progress (h)، افراد درگیر، AI، Backend، Front-end،
    DevOps، UI / UX، تاریخ ایجاد، تاریخ شروع پیاده سازی، ددلاین، اسپرینت، وابستگی ها،
    زمان تحویل اولیه، توضیحات، معیارهای پذیرش، تست ها، علل تغییر یا توقف،
    [individual developer columns], jira_issue_key، developer_board_issue_key
    """

    row_number: int = Field(description="ردیف - Row number")
    task_title: str = Field(description="وظیفه - Task title/summary")
    epic: Optional[str] = Field(default=None, description="Epic - Epic name")
    necessity: Optional[str] = Field(
        default=None,
        description="ضرورت - Necessity level (Must-have, Should-have, etc.)",
    )
    release: Optional[str] = Field(default=None, description="ریلیز - Release/Fix Version")
    departments: List[str] = Field(default_factory=list, description="Departments - Components")
    status: str = Field(description="وضعیت - Status")
    priority: Optional[str] = Field(default=None, description="اولویت - Priority")
    department_deps: Optional[str] = Field(
        default=None,
        description="Department Deps - Department dependencies",
    )
    main_release: Optional[str] = Field(
        default=None,
        description="ریلیز اصلی - Main release",
    )
    eta_hours: float = Field(default=0.0, description="ETA(h) - Estimated hours")
    total_hours: float = Field(default=0.0, description="Total (h) - Total time in hours")
    progress_hours: float = Field(default=0.0, description="Progress (h) - Time logged in hours")
    involved_people: List[str] = Field(
        default_factory=list,
        description="افراد درگیر - Involved people from worklogs",
    )
    ai_hours: float = Field(default=0.0, description="AI - Hours by AI team")
    backend_hours: float = Field(default=0.0, description="Backend - Hours by backend team")
    frontend_hours: float = Field(default=0.0, description="Front-end - Hours by frontend team")
    devops_hours: float = Field(default=0.0, description="DevOps - Hours by DevOps team")
    ui_ux_hours: float = Field(default=0.0, description="UI / UX - Hours by UI/UX team")
    created_date: Optional[datetime] = Field(default=None, description="تاریخ ایجاد - Created date")
    implementation_start_date: Optional[datetime] = Field(
        default=None,
        description="تاریخ شروع پیاده سازی - Implementation start date",
    )
    deadline: Optional[datetime] = Field(default=None, description="ددلاین - Deadline/Due date")
    sprint: Optional[str] = Field(default=None, description="اسپرینت - Sprint name")
    dependencies: Optional[str] = Field(
        default=None,
        description="وابستگی ها - Dependencies",
    )
    initial_delivery_time: Optional[datetime] = Field(
        default=None,
        description="زمان تحویل اولیه - Initial delivery time",
    )
    description: Optional[str] = Field(default=None, description="توضیحات - Description")
    acceptance_criteria: Optional[str] = Field(
        default=None,
        description="معیارهای پذیرش - Acceptance criteria",
    )
    tests: Optional[str] = Field(default=None, description="تست ها - Tests")
    change_reasons: Optional[str] = Field(
        default=None,
        description="علل تغییر یا توقف - Change or pause reasons",
    )
    individual_hours: Dict[str, float] = Field(
        default_factory=dict,
        description="Individual developer hours mapped by name",
    )
    jira_issue_key: str = Field(description="jira_issue_key - Jira PM board issue key")
    developer_board_issue_key: str = Field(
        description="developer_board_issue_key - Jira developer board issue key",
    )

    class Config:
        frozen = False
