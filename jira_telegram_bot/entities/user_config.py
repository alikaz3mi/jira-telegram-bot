from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import BaseModel


class FieldConfig(BaseModel):
    set_field: bool = True
    values: Optional[List[str]] = None


class UserConfig(BaseModel):
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
        values=["Highest", "High", "Medium", "Low", "Lowest"],
    )
    deadline: FieldConfig = FieldConfig(
        set_field=True,
        values=[
            "0",
            "1",
            "2",
            "3",
            "5",
            "8",
            "13",
            "21",
            "30",
        ],  # Default deadline options in days
    )
    labels: FieldConfig = FieldConfig(
        set_field=True,
        values=[
            "Must-have",
            "Should-Have",
            "Could-Have",
            "Won't-Have",
        ],  # Common default labels
    )

    # Advanced task creation settings
    advanced_task: FieldConfig = FieldConfig(
        set_field=True,
        values=["AI", "Backend", "Frontend", "DevOps", "UI/UX"],  # Default components
    )
    story_splitting: FieldConfig = FieldConfig(
        set_field=True,
        values=["2", "3", "5", "8", "13"],  # Default story point options
    )
    task_decomposition: FieldConfig = FieldConfig(
        set_field=True,
        values=["0.5", "1", "2", "3", "5", "8"],  # Default subtask point options
    )
    voice_input: FieldConfig = FieldConfig(set_field=True)
    auto_assign: FieldConfig = FieldConfig(set_field=True)
