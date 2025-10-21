from datetime import datetime
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class BugImprovementSheetRow(BaseModel):
    """Entity representing a row in the bug/improvement Google Sheet.
    
    Column order matches the Google Sheet structure:
    ردیف، وظیفه، توضیحات، گزارش دهنده، برد، افراد درگیر، اسپرینت، Epic، Story، 
    اولویت، وضعیت، Departments، ریلیز، Total (h)، تاریخ ایجاد، تاریخ شروع پیاده سازی، 
    ددلاین، یوزر درگیر، زمان تحویل اولیه، issue_key
    """

    row_number: int = Field(description="ردیف - Row number")
    task_title: str = Field(description="وظیفه - Task title/summary")
    description: Optional[str] = Field(default=None, description="توضیحات - Description")
    reporter: Optional[str] = Field(default=None, description="گزارش دهنده - Reporter")
    board_name: Optional[str] = Field(default=None, description="برد - Board name")
    involved_people: List[str] = Field(default_factory=list, description="افراد درگیر - Involved people from subtasks")
    sprint: Optional[str] = Field(default=None, description="اسپرینت - Sprint name")
    epic_name: Optional[str] = Field(default=None, description="Epic - Epic name")
    linked_story: Optional[str] = Field(default=None, description="Story - Linked story key")
    priority: Optional[str] = Field(default=None, description="اولویت - Priority")
    status: str = Field(description="وضعیت - Status")
    departments: List[str] = Field(default_factory=list, description="Departments - Components")
    release: Optional[str] = Field(default=None, description="ریلیز - Release/Fix Version")
    total_hours: float = Field(default=0.0, description="Total (h) - Total time in hours")
    created_date: Optional[datetime] = Field(default=None, description="تاریخ ایجاد - Created date")
    implementation_start_date: Optional[datetime] = Field(
        default=None,
        description="تاریخ شروع پیاده سازی - Implementation start date",
    )
    deadline: Optional[datetime] = Field(default=None, description="ددلاین - Deadline/Due date")
    involved_user_from_label: Optional[str] = Field(
        default=None,
        description="یوزر درگیر - User ID from #ID label",
    )
    initial_delivery_time: Optional[datetime] = Field(
        default=None,
        description="زمان تحویل اولیه - Initial delivery time (when moved to Done)",
    )
    issue_key: str = Field(description="issue_key - Jira issue key")

    class Config:
        frozen = False
