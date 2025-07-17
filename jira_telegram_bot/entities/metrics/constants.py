"""Constants for metrics tracking."""

from enum import Enum


class MetricType(str, Enum):
    """Types of metrics that can be tracked."""
    
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_RESOLVED = "task_resolved"
    TASK_REOPENED = "task_reopened"
    TASK_TRANSITIONED = "task_transitioned"
    TIME_LOGGED = "time_logged"
    COMMIT_MADE = "commit_made"
    MERGE_REQUEST_OPENED = "merge_request_opened"
    MERGE_REQUEST_MERGED = "merge_request_merged"
    MERGE_REQUEST_CLOSED = "merge_request_closed"
    DEADLINE_HIT = "deadline_hit"
    DEADLINE_MISSED = "deadline_missed"


class SheetName(str, Enum):
    """Names of different Google Sheets for metrics."""
    
    DAILY_SCOREBOARD = "daily_scoreboard"
    DEVELOPER_METRICS_MATRIX = "developer_metrics_matrix"
