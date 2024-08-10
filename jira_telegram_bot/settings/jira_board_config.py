from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class JiraBoardSettings(BaseSettings):
    board_name: str = Field("name of the jira board")
    assignees: List[str] = Field("List of users of the Jira board")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="jira_board_",
        extra="ignore",
    )
