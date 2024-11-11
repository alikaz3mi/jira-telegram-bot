from __future__ import annotations

from pydantic import BaseModel

from jira_telegram_bot.entities.field_config import FieldConfig


class UserConfig(BaseModel):
    telegram_username: str
    jira_username: str
    project: FieldConfig
    component: FieldConfig
    task_type: FieldConfig
    story_point: FieldConfig
    attachment: FieldConfig
    epic_link: FieldConfig
    release: FieldConfig
    sprint: FieldConfig
