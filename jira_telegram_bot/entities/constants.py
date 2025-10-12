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

# High Priority Task Requirements
MIN_HIGH_PRIORITY_TASKS_PER_WEEK = 1
HIGH_PRIORITY_ZERO_COMPLETION_PENALTY = -50  # Severe penalty for zero completion
HIGH_PRIORITY_BELOW_MIN_SCORE = 20           # Low score for below minimum

# Deadline calculation (days instead of hours)
DEADLINE_PENALTY_PER_DAY = 2.0    # Points deducted per day late
EARLY_DELIVERY_BONUS_PER_DAY = 1.0  # Points added per day early
MAX_EARLY_DELIVERY_BONUS = 110    # Maximum score with early delivery bonus

DEFAULT_DEADLINE_PENALTY_RATE = 2.0  # 2 points per hour late (deprecated - use per day)

# Task overload handling
EXTRA_TASK_COMPLETION_BONUS = 3.0  # Bonus points per extra task completed beyond capacity

# Default workweek configuration
DEFAULT_WEEKLY_HOURS = 46.0
DEFAULT_WORKDAYS = (6, 0, 1, 2, 3, 5)  # Sat-Thu (Saturday=6, Sunday=0, etc.)
DEFAULT_TIMEZONE = "Asia/Tehran"

# Expected hours mode
EXPECTED_HOURS_WEEKLY = "weekly"
EXPECTED_HOURS_TOTAL = "total"

# Department inference strategies
DEPT_INFERENCE_COMPONENT = "component"
DEPT_INFERENCE_LABEL = "label" 
DEPT_INFERENCE_USER_CONFIG = "user_config"
