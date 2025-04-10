from __future__ import annotations

from pydantic import BaseModel

from jira_telegram_bot.entities.field_config import FieldConfig


class UserConfig(BaseModel):
    telegram_username: str
    telegram_user_chat_id: int
    jira_username: str
    project: FieldConfig
    component: FieldConfig
    task_type: FieldConfig
    story_point: FieldConfig
    attachment: FieldConfig
    epic_link: FieldConfig
    release: FieldConfig
    sprint: FieldConfig
    assignee: FieldConfig
    labels: FieldConfig = FieldConfig(default=FieldConfig(set_field=False))
    deadline: FieldConfig = FieldConfig(default=FieldConfig(set_field=False))
    priority: FieldConfig = FieldConfig(default=FieldConfig(set_field=True))
