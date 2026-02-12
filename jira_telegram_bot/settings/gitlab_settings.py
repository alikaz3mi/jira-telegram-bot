from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class GitlabSettings(BaseSettings):
    """
    Pydantic settings for GitLab connection.

    These fields will be loaded from environment variables in .env:
      - GITLAB_URL
      - GITLAB_ACCESS_TOKEN
      - GITLAB_PROJECT_NAME_FILTERS
    """

    url: str = Field(..., env="GITLAB_URL")
    access_token: str = Field(..., env="GITLAB_ACCESS_TOKEN")
    project_name_filters: list[str] = Field(
        default_factory=list,
        env="GITLAB_PROJECT_NAME_FILTERS",
        description="Lowercase substrings to match GitLab project names against.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="gitlab_",
        extra="ignore",
    )
