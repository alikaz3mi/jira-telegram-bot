from pydantic_settings import SettingsConfigDict
from pydantic import Field, HttpUrl
from typing import Optional
from pydantic_settings import BaseSettings

from enum import Enum

class JiraConnectionType(Enum):
    CLOUD = "cloud"
    SELF_HOSTED = "self_hosted"


class JiraConnectionSettings(BaseSettings):
    username: str = Field(description="Jira username")
    password: str = Field(default=None, description="Jira password")
    email: Optional[str] = Field(default=None, description="Jira email")
    domain: HttpUrl = Field(
        description="Jira domain (e.g., https://your-domain.atlassian.net)",
        default=None,
    )
    token: Optional[str] = Field(
        description="Jira token",
        default=None,
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="jira_", extra="ignore"
    )
    
    @property
    def connection_type(self) -> JiraConnectionType:
        """Determine if the Jira instance is cloud-based or self-hosted.
        
        Returns:
            JiraConnectionType: CLOUD if domain contains 'atlassian.net', SELF_HOSTED otherwise.
        """
        return JiraConnectionType.CLOUD if "atlassian.net" in self.domain.host else JiraConnectionType.SELF_HOSTED
