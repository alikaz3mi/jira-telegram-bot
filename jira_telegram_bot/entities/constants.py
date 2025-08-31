"""Constants for team evaluation functionality."""

from typing import Set

# Issue type groups
DEV_ISSUE_TYPES: Set[str] = {"Task", "Sub-task", "Improvement"}
BUG_ISSUE_TYPES: Set[str] = {"Bug"}
SUPPORT_LABELS: Set[str] = {"Support"}
SUPPORT_EPIC_NAME: str = "پشتیبانی مشتریان"

# Priority levels
HIGH_PRIORITY: str = "Highest"

# Status groups
REVIEW_STATUSES: Set[str] = {"Review", "In Review", "Code Review"}
BACKLOG_STATUSES: Set[str] = {"Backlog", "To Do", "In Progress", "Selected for Development"}
DONE_STATUSES: Set[str] = {"Done", "Resolved", "Closed"}

# Defect labels
TESTER_LABEL: str = "tester"

# Default score computation parameters
DEFAULT_DEFECT_THRESHOLDS = {
    "support_per_story": 0.3,
    "tester_per_story": 0.4,
    "max_penalty": 60
}

DEFAULT_DEADLINE_PENALTY_RATE = 2.0  # 2 points per hour late

# Default workweek configuration
DEFAULT_WEEKLY_HOURS = 46.0
DEFAULT_WORKDAYS = (6, 0, 1, 2, 3, 4)  # Sat-Thu (Saturday=6, Sunday=0, etc.)
DEFAULT_TIMEZONE = "Asia/Tehran"

# Expected hours mode
EXPECTED_HOURS_WEEKLY = "weekly"
EXPECTED_HOURS_TOTAL = "total"

# Department inference strategies
DEPT_INFERENCE_COMPONENT = "component"
DEPT_INFERENCE_LABEL = "label" 
DEPT_INFERENCE_USER_CONFIG = "user_config"
