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
    """

    url: str = Field(..., env="GITLAB_URL")
    access_token: str = Field(..., env="GITLAB_ACCESS_TOKEN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="gitlab_",
        extra="ignore",
    )
