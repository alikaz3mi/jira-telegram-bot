from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class PostgresSettings(BaseSettings):
    """
    Pydantic settings for PostgreSQL connection.
    These fields will be loaded from environment variables in .env:
      - POSTGRES_USER
      - POSTGRES_PASSWORD
      - POSTGRES_HOST
      - POSTGRES_PORT
      - POSTGRES_DB
    """

    db_user: str = Field(...)
    db_password: str = Field(...)
    db_host: str = Field(...)
    db_port: int = Field(...)
    db_name: str = Field(...)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
