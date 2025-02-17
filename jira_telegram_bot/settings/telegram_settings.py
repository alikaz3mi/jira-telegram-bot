from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class TelegramConnectionSettings(BaseSettings):
    TOKEN: str = Field(description="Telegram Bot Token")
    ALLOWED_USERS: List[str] = Field(
        description="List of telegram users that are authorized to create task",
    )
    WEBHOOK_URL: str = Field(description="Telegram Webhook URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TELEGRAM_",
        extra="ignore",
    )


class TelegramWebhookConnectionSettings(BaseSettings):
    TOKEN: str = Field(description="Telegram Bot Token")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TELEGRAM_HOOK_",
        extra="ignore",
    )
