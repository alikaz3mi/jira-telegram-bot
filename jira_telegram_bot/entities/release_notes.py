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
    description: str = Field(description="شرح")
    goals: Optional[str] = Field(default=None, description="اهداف")
    delivery_process: Optional[str] = Field(default=None, description="فرایند تحویل")
    test_process: Optional[str] = Field(default=None, description="فرایند تست")
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
