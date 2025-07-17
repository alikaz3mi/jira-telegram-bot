"""Daily metric row entity for Google Sheets daily scoreboard."""

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, Field


class DailyMetricRow(BaseModel):
    """Immutable daily metrics row for Google Sheets.
    
    Args:
        developer_name: Display name of the developer
        metric_date: Date for the metrics
        today_deadlines: Number of deadlines today
        resolved_tasks: Number of tasks resolved today
        logged_time: Hours logged today
        commits: Number of commits made today
        comments: Latest comment or description of work
    """
    
    developer_name: str = Field(description="Display name of the developer")
    metric_date: Date = Field(description="Date for the metrics")
    today_deadlines: int = Field(default=0, description="Number of deadlines today")
    resolved_tasks: int = Field(default=0, description="Number of tasks resolved today")
    logged_time: float = Field(default=0.0, description="Hours logged today")
    commits: int = Field(default=0, description="Number of commits made today")
    comments: Optional[str] = Field(default=None, description="Latest comment or work description")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
