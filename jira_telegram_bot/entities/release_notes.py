"""Entity for Release Notes sheet data."""

from __future__ import annotations

from datetime import datetime
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot import LOGGER


class ReleaseNoteEntity(BaseModel):
    """Entity representing a release note from Google Sheets."""
    
    row_number: int = Field(description="Row number in the sheet")
    release_version: str = Field(description="ریلیز اصلی (e.g., V 1.0.0)")
    release_components: str = Field(description="اجزای ریلیز")
    person_hours: Optional[str] = Field(default=None, description="نفر ساعت")
    involved_people: Optional[str] = Field(default=None, description="افراد درگیر")
    epic: Optional[str] = Field(default=None, description="Epic")
    percent_complete: Optional[str] = Field(default=None, description="% Complete")
    status: Optional[str] = Field(default=None, description="وضعیت")
    rag: Optional[str] = Field(default=None, description="RAG")
    description: str = Field(description="شرح")
    goals: Optional[str] = Field(default=None, description="اهداف")
    delivery_process: Optional[str] = Field(default=None, description="فرایند تحویل")
    test_process: Optional[str] = Field(default=None, description="فرایند تست")
    start_date: Optional[str] = Field(default=None, description="تاریخ شروع")
    alpha_plan: Optional[str] = Field(default=None, description="Alpha Plan")
    alpha_delivery: Optional[str] = Field(default=None, description="Alpha Delivery")
    beta_plan: Optional[str] = Field(default=None, description="Beta Plan")
    beta_delivery: Optional[str] = Field(default=None, description="Beta Delivery")
    freeze: Optional[str] = Field(default=None, description="Freeze")
    env_dev: Optional[str] = Field(default=None, description="Env Dev ✅")
    env_staging: Optional[str] = Field(default=None, description="Env Staging ✅")
    env_prod: Optional[str] = Field(default=None, description="Env Prod ✅")
    total_issues: Optional[str] = Field(default=None, description="Total Issues")
    done_issues: Optional[str] = Field(default=None, description="Done Issues")
    blockers: Optional[str] = Field(default=None, description="Blockers")
    delay_days: Optional[str] = Field(default=None, description="Delay Days")
    test_pass_rate: Optional[str] = Field(default=None, description="Test Pass Rate (0-1)")
    sev1_open: Optional[str] = Field(default=None, description="Sev1 Open")
    sev2_open: Optional[str] = Field(default=None, description="Sev2 Open")
    pipeline_green_rate: Optional[str] = Field(default=None, description="Pipeline Green Rate (0-1)")
    checklist_completion: Optional[str] = Field(default=None, description="Checklist Completion (0-1)")
    readiness_score: Optional[str] = Field(default=None, description="Readiness Score (0-100)")
    notes_risks: Optional[str] = Field(default=None, description="Notes / Risks")
    documentation_link: Optional[str] = Field(default=None, description="لینک Documentation")
    telegram_message_id: Optional[str] = Field(default=None, description="Telegram message ID for tracking edits")
    last_updated: Optional[datetime] = Field(default=None, description="Last update timestamp")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class SprintInfo(BaseModel):
    """Entity representing sprint information."""
    
    sprint_id: str = Field(description="Sprint identifier")
    start_date: str = Field(description="Persian start date")
    end_date: str = Field(description="Persian end date")
    
    @classmethod
    def parse_sprint_string(cls, sprint_string: str) -> Optional['SprintInfo']:
        """Parse sprint string in format: <sprint-id>: <Persian-date start>: <Persian-date end>
        
        Args:
            sprint_string: Sprint string to parse
            
        Returns:
            SprintInfo if parsing successful, None otherwise
        """
        if not sprint_string or sprint_string.strip() == "Select":
            return None
            
        try:
            parts = sprint_string.split(":")
            if len(parts) >= 3:
                sprint_id = parts[0].strip()
                start_date = parts[1].strip()
                end_date = parts[2].strip()
                
                return cls(
                    sprint_id=sprint_id,
                    start_date=start_date,
                    end_date=end_date
                )
            if len(parts) == 2:
                # Handle case with only start and end dates
                sprint_id = parts[0].strip()
                start_date, end_date = parts[1].split(' to ')
                
                return cls(
                    sprint_id=sprint_id,
                    start_date=start_date.strip(),
                    end_date=end_date.strip()
                )
        except Exception as e:
            LOGGER.error(f"Error parsing sprint string '{sprint_string}': {e}")
            
        return None
    
    def is_valid(self) -> bool:
        """Check if sprint info is valid for creation."""
        return bool(self.sprint_id and self.start_date and self.end_date)
    
    class Config:
        """Pydantic configuration."""
        frozen = True
