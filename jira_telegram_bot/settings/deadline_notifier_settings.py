from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class DeadlineNotifierSettings(BaseSettings):
    """Settings for deadline notifier configuration."""

    LOOKAHEAD_DAYS: int = Field(
        default=7,
        description="Number of days to look ahead for deadlines",
    )
    ADDITIONAL_JQL: str = Field(
        default="",
        description="Additional JQL filter to apply to deadline queries",
    )
    CRON_SCHEDULE: str = Field(
        default="0 9 * * *",
        description="Cron schedule for deadline notifications (default: 9 AM daily)",
    )
    GROUP_NOTIFICATION_USERNAMES: List[str] = Field(
        default=[],
        description="List of Jira usernames who receive group notifications with filtered content",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DEADLINE_NOTIFIER_",
        extra="ignore",
    )
