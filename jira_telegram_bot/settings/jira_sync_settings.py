"""Settings for Jira synchronization service."""
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class JiraSyncSettings(BaseSettings):
    """Configuration for Jira data synchronization to PostgreSQL."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    sync_interval_minutes: int = Field(
        default=10,
        description="Interval in minutes between sync operations"
    )

    sync_project_keys: List[str] = Field(
        default_factory=lambda: ["PROJECT1", "PROJECT2"],
        description="List of Jira project keys to synchronize"
    )

    sync_full_sync: bool = Field(
        default=True,
        description="Whether to perform full sync or incremental sync"
    )

    pm_project_key: str = Field(
        default="",
        description="Jira project key for the PM board used to find linked issues"
    )
