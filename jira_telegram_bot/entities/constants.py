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
HIGH_PRIORITY_ZERO_COMPLETION_PENALTY = -50  # Severe penalty for zero completion
HIGH_PRIORITY_BELOW_MIN_SCORE = 20           # Low score for below minimum

# Deadline calculation (days instead of hours)
MAX_EARLY_DELIVERY_BONUS = 110    # Maximum score with early delivery bonus


# Task overload handling
EXTRA_TASK_COMPLETION_BONUS = 3.0  # Bonus points per extra task completed beyond capacity

# Required tasks calculation
REQUIRED_TASKS_HOURS_RATIO = 0.5  # 50% of weekly hours for required tasks

# Deadline penalty configuration
DEADLINE_GRACE_PERIOD_DAYS = 2  # Grace period before penalties apply
UNDELIVERED_TASK_DELAY_DAYS = 1  # Assume undelivered tasks are 1 day after sprint end

# Dynamic penalty coefficient (based on task count)
PENALTY_COEFFICIENT_MAX = 15.0  # Maximum penalty coefficient (1 task)
PENALTY_COEFFICIENT_MIN = 5.0   # Minimum penalty coefficient (10+ tasks)
PENALTY_COEFFICIENT_TASK_THRESHOLD = 9  # Task count threshold for minimum penalty

# Priority weight multipliers for deadline penalties
PRIORITY_WEIGHT_HIGHEST = 1.0
PRIORITY_WEIGHT_HIGH = 0.6
PRIORITY_WEIGHT_OTHERS = 0.2

# Time registration thresholds and penalties
TIME_REGISTRATION_THRESHOLD = 0.65  # 65% of minimum required hours
TIME_REGISTRATION_PENALTY_BASE = 30  # Base penalty for no time registration
TIME_REGISTRATION_PENALTY_MULTIPLIER = 30  # Multiplier for shortage percentage

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
