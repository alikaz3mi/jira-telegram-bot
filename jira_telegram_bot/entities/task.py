from __future__ import annotations

from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from jira_telegram_bot.entities.constants import JiraField


class JiraIssueReference(BaseModel):
    """Pure domain model to replace external jira.Issue dependency."""
    
    key: str
    summary: str
    description: Optional[str] = None
    issue_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    
    @classmethod
    def from_raw_issue(cls, raw_issue: Dict[str, Any]) -> "JiraIssueReference":
        """Create from raw API response or dictionary representation."""
        fields = raw_issue.get("fields", {})
        return cls(
            key=raw_issue.get("key", ""),
            summary=fields.get("summary", ""),
            description=fields.get("description", ""),
            issue_type=fields.get("issuetype", {}).get("name") if fields.get("issuetype") else None,
            priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
            status=fields.get("status", {}).get("name") if fields.get("status") else None,
            assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            labels=fields.get("labels", []),
            components=[c.get("name", "") for c in fields.get("components", []) if c.get("name")],
        )


class TaskData(BaseModel):
    """Data required to create or update a task in the task management system."""
    
    project_key: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    component: Optional[str] = Field(default=None)  # TODO: omit this one
    components: Optional[List[str]] = Field(default=None)
    labels: Optional[List[str]] = Field(default_factory=list)
    task_type: Optional[str] = Field(default=None)
    story_points: Optional[float] = Field(default=None)
    sprint_id: Optional[int] = Field(default=None)
    sprint_name: Optional[str] = Field(default=None)
    epic_link: Optional[str] = Field(default=None)
    release: Optional[str] = Field(default=None)
    assignee: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    create_another: bool = Field(default=False)
    parent_issue_key: Optional[str] = Field(default=None)
    attachments: Dict[str, List] = Field(
        default_factory=lambda: {
            "images": [],
            "videos": [],
            "audio": [],
            "documents": [],
        },
    )
    config: Dict[str, Any] = Field(default_factory=dict)
    epics: List[JiraIssueReference] = Field(default_factory=list)
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

    def to_jira_fields(self) -> Dict[str, Any]:
        """Convert the domain model to fields used in Jira API."""
        fields = {
            "project": {"key": self.project_key} if self.project_key else None,
            "summary": self.summary,
            "description": self.description,
            "issuetype": {"name": self.task_type} if self.task_type else None,
        }
        
        # Only add non-None fields
        if self.components:
            fields["components"] = [{"name": c} for c in self.components]
        elif self.component:  # fallback to single component
            fields["components"] = [{"name": self.component}]
            
        if self.labels:
            fields["labels"] = self.labels
            
        if self.assignee:
            fields["assignee"] = {"name": self.assignee}
            
        if self.priority:
            fields["priority"] = {"name": self.priority}
            
        if self.story_points is not None:
            fields[JiraField.STORY_POINTS.value] = self.story_points
            
        if self.epic_link:
            fields[JiraField.EPIC_LINK.value] = self.epic_link
            
        if self.target_end:
            fields[JiraField.TARGET_END.value] = self.target_end
            
        if self.parent_issue_key:
            fields["parent"] = {"key": self.parent_issue_key}
            
        return {k: v for k, v in fields.items() if v is not None}

    model_config = ConfigDict(arbitrary_types_allowed=True)
