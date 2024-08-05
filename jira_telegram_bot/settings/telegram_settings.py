from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class TelegramConnectionSettings(BaseSettings):
    TOKEN: str = Field(description="Telegram Bot Token")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TELEGRAM_",
        extra="ignore",
    )
