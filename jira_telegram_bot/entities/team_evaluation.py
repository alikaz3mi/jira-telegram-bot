"""Team evaluation domain entities."""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Department(str, Enum):
    """Department enumeration."""
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    DEVOPS = "DevOps"
    DATA = "Data"
    PRODUCT = "Product"
    QA = "QA"
    MOBILE = "Mobile"


class IssueTypeGroup(str, Enum):
    """Issue type groups for classification."""
    DEV_GROUP = "development"
    BUG_GROUP = "bug"
    SUPPORT_GROUP = "support"


class StatusGroup(str, Enum):
    """Status groups for classification."""
    BACKLOG = "backlog"
    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class PriorityLevel(str, Enum):
    """Priority levels."""
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


class TeamEvaluationScoreWeights(BaseModel):
    """Score weights for team evaluation computation."""
    deadline: float = Field(default=0.35, ge=0, le=1)
    worklog: float = Field(default=0.25, ge=0, le=1)
    high_priority: float = Field(default=0.20, ge=0, le=1)
    defects: float = Field(default=0.20, ge=0, le=1)

    def model_post_init(self, __context: Any) -> None:
        """Validate that weights sum to 1.0."""
        total = self.deadline + self.worklog + self.high_priority + self.defects
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Score weights must sum to 1.0, got {total}")


class SprintClosedEvent(BaseModel):
    """Event representing a closed sprint."""
    sprint_id: int
    sprint_name: str
    project_keys: List[str]
    ended_at: datetime


class WorklogSlice(BaseModel):
    """Worklog entry for an issue."""
    issue_key: str
    author: str
    started_at: datetime
    hours: float


class ChangeLogEvent(BaseModel):
    """Change log event for status transitions."""
    issue_key: str
    field: str
    from_status: Optional[str]
    to_status: Optional[str]
    changed_at: datetime
    author: str


class IssueSnapshot(BaseModel):
    """Minimal issue projection for team evaluation."""
    key: str
    issue_type: str
    priority: Optional[str]
    labels: List[str]
    components: List[str]
    epic_key: Optional[str]
    epic_name: Optional[str]
    due_date: Optional[datetime]
    status: str
    assignee: Optional[str]
    project_key: str
    project_name: str
    resolution_date: Optional[datetime]
    created_date: datetime
    updated_date: datetime
    linked_issues: List[str] = Field(default_factory=list)


class TeamEvaluationRow(BaseModel):
    """Team evaluation row data for Google Sheets."""
    developer_name: str  # توسعه دهنده
    department: str  # دپارتمان
    project: str  # پروژه
    sprint: str  # اسپرینت
    development_count: int  # توسعه
    bug_count: int  # باگ
    support_count: int  # پشتیبانی
    high_priority_count: int  # تسکهای اولویت بالا
    registered_hours_week: float  # زمان ثبت شده هفته
    expected_hours_week: float  # زمان انتظاری هفته
    bug_hours: float  # زمان باگ
    development_hours: float  # زمان توسعه
    support_hours: float  # زمان پشتیبانی
    avg_deadline_delivery_hours: str  # میانگین ددلاین دلیوری به ساعت
    review_back_count: int  # بازگشت از مرور به بک لاگ
    story_test_pass_rate: str  # درصد پاس شدن تست استوری
    acceptance_criteria_pass_rate: str  # درصد پاس شدن معیارهای پذیرش
    high_priority_completed_count: int  # تسکهای اولویت بالا تکمیل شده
    avg_support_bugs_per_story: float  # میانگین باگهای ثبت شده برای استوری های از پشتیبانی
    avg_tester_bugs_per_story: float  # میانگین باگهای ثبت شده در یوزر استوری توسط تستر
    development_delivered_count: int  # توسعه تحویل داده شده
    bug_delivered_count: int  # باگ تحویل داده شده
    support_delivered_count: int  # پشتیبانی تحویل داده شده
    quality_score: int  # درصد حسن انجام کار

    def to_sheet_row(self) -> List[str]:
        """Convert to sheet row format with Farsi headers."""
        return [
            self.developer_name,
            self.department,
            self.project,
            self.sprint,
            str(self.development_count),
            str(self.bug_count),
            str(self.support_count),
            str(self.high_priority_count),
            str(round(self.registered_hours_week, 1)),
            str(round(self.expected_hours_week, 1)),
            str(round(self.bug_hours, 1)),
            str(round(self.development_hours, 1)),
            str(round(self.support_hours, 1)),
            self.avg_deadline_delivery_hours,
            str(self.review_back_count),
            self.story_test_pass_rate,
            self.acceptance_criteria_pass_rate,
            str(self.high_priority_completed_count),
            str(round(self.avg_support_bugs_per_story, 2)),
            str(round(self.avg_tester_bugs_per_story, 2)),
            str(self.development_delivered_count),
            str(self.bug_delivered_count),
            str(self.support_delivered_count),
            str(self.quality_score),
        ]

    @classmethod
    def get_sheet_headers(cls) -> List[str]:
        """Get Farsi headers for the sheet."""
        return [
            "توسعه دهنده",
            "دپارتمان",
            "پروژه",
            "اسپرینت",
            "توسعه",
            "باگ",
            "پشتیبانی",
            "تسکهای اولویت بالا",
            "زمان ثبت شده هفته",
            "زمان انتظاری هفته",
            "زمان باگ",
            "زمان توسعه",
            "زمان پشتیبانی",
            "میانگین ددلاین دلیوری به ساعت",
            "بازگشت از مرور به بک لاگ",
            "درصد پاس شدن تست استوری",
            "درصد پاس شدن معیارهای پذیرش",
            "تسکهای اولویت بالا تکمیل شده",
            "میانگین باگهای ثبت شده برای استوری های از پشتیبانی",
            "میانگین باگهای ثبت شده در یوزر استوری توسط تستر",
            "توسعه تحویل داده شده",
            "باگ تحویل داده شده",
            "پشتیبانی تحویل داده شده",
            "درصد حسن انجام کار",
        ]
