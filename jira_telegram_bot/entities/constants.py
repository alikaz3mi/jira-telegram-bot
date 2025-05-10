from __future__ import annotations

from enum import Enum, auto


class JiraField(Enum):
    """Jira field identifiers for custom fields."""
    STORY_POINTS = "customfield_10106"
    TARGET_END = "customfield_10110"
    SPRINT = "customfield_10100"
    EPIC_LINK = "customfield_10101"


class TaskType(Enum):
    """Standard Jira issue types."""
    TASK = "Task"
    BUG = "Bug"
    STORY = "Story"
    EPIC = "Epic"
    SUBTASK = "Sub-task"


class TaskPriority(Enum):
    """Standard Jira priority values."""
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


class TaskStatus(Enum):
    """Common Jira workflow statuses."""
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    BACKLOG = "Backlog"
    SELECTED_FOR_DEVELOPMENT = "Selected for Development"
    CODE_REVIEW = "Code Review"
    TESTING = "Testing"


class LabelCategory(Enum):
    """Common label categories used in tasks."""
    MUST_HAVE = "Must-have"
    SHOULD_HAVE = "Should-Have"
    COULD_HAVE = "Could-Have"
    WONT_HAVE = "Won't-Have"


class TeamComponent(Enum):
    """Standard team components used in projects."""
    AI = "AI"
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    DEVOPS = "DevOps"
    UI_UX = "UI/UX"


# Time estimation constants
DEFAULT_STORY_POINTS = ["1", "2", "3", "5", "8", "13", "21"]
DEFAULT_SUBTASK_POINTS = ["0.5", "1", "2", "3", "5", "8"]
DEFAULT_DEADLINE_OPTIONS = ["0", "1", "2", "3", "5", "8", "13", "21", "30"]  # Days