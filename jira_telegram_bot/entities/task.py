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
    project_key: Optional[str] | None = Field(default=None)
    summary: Optional[str] | None = Field(default=None)
    description: Optional[str] | None = Field(default=None)
    component: Optional[str] | None = Field(default=None)
    task_type: Optional[str] | None = Field(default=None)
    story_points: Optional[float] | None = Field(default=None)
    sprint_id: Optional[int] | None = Field(default=None)
    epic_link: Optional[str] | None = Field(default=None)
    release: Optional[str] | None = Field(default=None)
    attachments: Dict[str, List] = Field(
        default={"images": [], "videos": [], "audio": [], "documents": []},
    )
    config: Dict[str, Any] | None = Field(default=None)
    epics: List[Issue] | None = Field(default=None)
    board_id: Optional[int] | None = Field(default=None)
    media_group_messages: Dict[str, List[Any]] | None = Field(default=defaultdict(list))
    model_config = ConfigDict(arbitrary_types_allowed=True)
