"""Input and output models for test scenarios generation."""

from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class SynthPMTestScenario(BaseModel):
    """Model for a single test scenario."""
    
    test_number: str = Field(description="شماره تست (TC-01, TC-02, ...)")
    description: str = Field(description="توضیح روش تست")
    status: str = Field(default="⬜", description="وضعیت تست (همیشه ⬜)")
    responsible: str = Field(description="مسئول انجام تست (تستر یا توسعه‌دهنده)")


class GenerateTestScenariosInput(BaseModel):
    """Input model for test scenarios generation."""
    
    task_title: str = Field(description="عنوان تسک از Google Sheets")
    task_description: Optional[str] = Field(
        default=None,
        description="توضیحات تسک از Google Sheets"
    )
    user_story: Optional[str] = Field(
        default=None,
        description="یوزر استوری تولید شده قبلی"
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="معیارهای پذیرش تولید شده قبلی"
    )
    epic_name: Optional[str] = Field(
        default=None,
        description="نام اپیک مرتبط با تسک"
    )
    related_departments: List[str] = Field(
        default_factory=list,
        description="لیست دپارتمان‌های مرتبط با تسک"
    )
    project_info: Optional[str] = Field(
        default=None,
        description="اطلاعات کلی پروژه از projects_info.json"
    )


class GenerateTestScenariosResult(BaseModel):
    """Output model for test scenarios generation."""
    
    test_scenarios: List[SynthPMTestScenario] = Field(
        default_factory=list,
        description="لیست سناریوهای تست تولید شده"
    )
    metadata: Optional[dict] = Field(
        default_factory=dict,
        description="اطلاعات اضافی برای پیگیری و ترافیک"
    )
