"""Input and output models for acceptance criteria generation."""

from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class GenerateAcceptanceCriteriaInput(BaseModel):
    """Input model for acceptance criteria generation."""
    
    task_title: str = Field(description="عنوان تسک از Google Sheets")
    task_description: Optional[str] = Field(
        default=None,
        description="توضیحات تسک از Google Sheets"
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
    special_requirements: Optional[str] = Field(
        default=None,
        description="نیازمندی‌های خاص یا محدودیت‌ها"
    )


class GenerateAcceptanceCriteriaResult(BaseModel):
    """Output model for acceptance criteria generation."""
    
    user_story: str = Field(description="یوزر استوری تولید شده به فرم 'به‌عنوان ... می‌خواهم ... تا بتوانم ...'")
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="لیست معیارهای پذیرش به صورت بولت پوینت"
    )
    delivery_process: List[str] = Field(
        default_factory=list,
        description="مراحل فرایند تحویل از طراحی تا تحویل نهایی"
    )
    metadata: Optional[dict] = Field(
        default_factory=dict,
        description="اطلاعات اضافی برای پیگیری و ترافیک"
    )
