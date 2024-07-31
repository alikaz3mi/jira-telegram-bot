from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class ConnectionSettings(BaseSettings):
    username: str = Field(description="Jira username")
    password: str = Field(description="Jira password")
    domain: str = Field(description="Jira_domain")
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="jira",
        extra="ignore"
    )