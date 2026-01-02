"""Settings for daily task tracker."""
from typing import Optional

from pydantic_settings import BaseSettings


class DailyTaskTrackerSettings(BaseSettings):
    """Settings for daily task tracker."""

    ENABLED: bool = True
    CRON_SCHEDULE: str = "0 9 * * *"
    TIMEZONE: str = "Asia/Tehran"
    EXCLUDE_WEEKENDS: bool = True
    EXCLUDE_HOLIDAYS: bool = True
    LOOKAHEAD_DAYS: int = 0
    REGRESSION_LOOKBACK_HOURS: int = 24
    
    class Config:
        env_prefix = "DAILY_TASK_TRACKER_"
        case_sensitive = True
