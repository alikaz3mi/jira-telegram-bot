from pydantic_settings import SettingsConfigDict
from pydantic import Field

from jira_telegram_bot.utils.pydantic_advanced_settings import CustomizedSettings


class JiraConnectionSettings(CustomizedSettings):
    username: str = Field(description="Jira username")
    password: str = Field(description="Jira password")
    domain: str = Field(description="Jira_domain")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="jira_", extra="ignore"
    )
