from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import BaseModel

from jira_telegram_bot.entities.constants import (
    DEFAULT_DEADLINE_OPTIONS,
    DEFAULT_STORY_POINTS,
    DEFAULT_SUBTASK_POINTS,
    LabelCategory,
    TaskPriority,
    TeamComponent,
)


class FieldConfig(BaseModel):
    """Configuration for a field in user preferences."""
    
    set_field: bool = True
    values: Optional[List[str]] = None


class UserConfig(BaseModel):
    """User configuration entity for personalizing Jira interactions."""
    
    telegram_username: str
    telegram_user_chat_id: int
    jira_username: str
    project: FieldConfig = FieldConfig()
    component: FieldConfig = FieldConfig()
    task_type: FieldConfig = FieldConfig()
    story_point: FieldConfig = FieldConfig()
    attachment: FieldConfig = FieldConfig()
    epic_link: FieldConfig = FieldConfig()
    release: FieldConfig = FieldConfig()
    sprint: FieldConfig = FieldConfig()
    assignee: FieldConfig = FieldConfig()
    priority: FieldConfig = FieldConfig(
        set_field=True,
        values=[priority.value for priority in TaskPriority],
    )
    deadline: FieldConfig = FieldConfig(
        set_field=True,
        values=DEFAULT_DEADLINE_OPTIONS,
    )
    labels: FieldConfig = FieldConfig(
        set_field=True,
        values=[label.value for label in LabelCategory],
    )

    # Advanced task creation settings
    advanced_task: FieldConfig = FieldConfig(
        set_field=True,
        values=[component.value for component in TeamComponent],
    )
    story_splitting: FieldConfig = FieldConfig(
        set_field=True,
        values=DEFAULT_STORY_POINTS,
    )
    task_decomposition: FieldConfig = FieldConfig(
        set_field=True,
        values=DEFAULT_SUBTASK_POINTS,
    )
    voice_input: FieldConfig = FieldConfig(set_field=True)
    auto_assign: FieldConfig = FieldConfig(set_field=True)
