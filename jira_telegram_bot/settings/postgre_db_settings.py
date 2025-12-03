from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


def find_root_env() -> Path:
    """Find the root .env file by searching up from current directory."""
    current = Path.cwd()
    
    # Search up to 3 levels for project root
    for _ in range(3):
        env_file = current / ".env"
        # Check if this looks like the project root (has jira_telegram_bot directory)
        if (current / "jira_telegram_bot").is_dir() and env_file.exists():
            return env_file
        if current.parent == current:  # Reached filesystem root
            break
        current = current.parent
    
    # Fallback to current directory .env
    return Path(".env")


class PostgresSettings(BaseSettings):
    """
    Pydantic settings for PostgreSQL connection.
    These fields will be loaded from environment variables in .env:
      - db_user
      - db_password
      - db_host
      - db_port
      - db_name
    """

    db_user: str = Field(...)
    db_password: str = Field(...)
    db_host: str = Field(...)
    db_port: int = Field(...)
    db_name: str = Field(...)

    model_config = SettingsConfigDict(
        env_file=find_root_env(),
        env_file_encoding="utf-8",
        extra="ignore",
    )
