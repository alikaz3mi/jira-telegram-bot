from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class TelegramConnectionSettings(BaseSettings):
    TOKEN: str = Field(description="Telegram Bot Token")
    ALLOWED_USERS: List[str] = Field(
        description="List of telegram users that are authorized to create task"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TELEGRAM_",
        extra="ignore",
    )
