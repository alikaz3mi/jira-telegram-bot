"""Enums and constants for daily task tracking status."""
from enum import Enum


class TaskCheckStatus(str, Enum):
    """Status of a task check."""

    SHOULD_BE_STARTED = "should_be_started"
    IN_PROGRESS = "in_progress"
    NEEDS_WORKLOG = "needs_worklog"
    STATUS_REGRESSED = "status_regressed"
    OK = "ok"


class DelayReason(str, Enum):
    """Reasons for task delay."""

    WAITING_APPROVAL = "waiting_approval"
    TECHNICAL_BLOCKER = "technical_blocker"
    OTHER_PRIORITIES = "other_priorities"
    MISSING_REQUIREMENTS = "missing_requirements"
    DEPENDENCY_NOT_READY = "dependency_not_ready"
    OTHER = "other"
