from __future__ import annotations

from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class TaskData(BaseModel):
    project_key: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    component: Optional[str] = Field(default=None)  # TODO: omit this one
    components: Optional[List[str]] = Field(default=None)
    labels: Optional[List[str]] = Field(default=None)
    task_type: Optional[str] = Field(default=None)
    story_points: Optional[float] = Field(default=None)
    sprint_id: Optional[int] = Field(default=None)
    sprint_name: Optional[str] = Field(default=None)
    epic_link: Optional[str] = Field(default=None)
    release: Optional[str] = Field(default=None)
    assignee: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    create_another: bool = Field(default=False)
    labels: Optional[List[str]] = Field(default_factory=list)
    attachments: Dict[str, List] = Field(
        default_factory=lambda: {
            "images": [],
            "videos": [],
            "audio": [],
            "documents": [],
        },
    )
    config: Dict[str, Any] | None = Field(default=None)
    epics: List[Issue] = Field(default_factory=list)
    board_id: Optional[int] = Field(default=None)

    due_date: Optional[str] = Field(
        default=None,
        description="The actual date for the task due_date in YYYY-MM-DD.",
    )

    # Same date stored in the target_end custom field
    target_end: Optional[str] = Field(
        default=None,
        description="The date in customfield_10110 (Target End).",
    )

    sprints: List[Any] = Field(default_factory=list)
    task_types: List[str] = Field(default_factory=list)
    media_group_messages: Dict[str, List[Any]] = Field(
        default_factory=lambda: defaultdict(list),
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
