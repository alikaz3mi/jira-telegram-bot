from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.utils.pydantic_advanced_settings import CustomizedSettings


class OpenAISettings(CustomizedSettings):
    token: str = Field(description="token of openai")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="openai_",
        extra="ignore",
    )
