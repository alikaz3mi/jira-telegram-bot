from __future__ import annotations

from enum import Enum


class JiraStatusConstants(Enum):
    """Constants for Jira issue statuses."""
    
    REVIEW = "Review"
    DONE = "Done"
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"


class JiraFieldConstants(Enum):
    """Constants for Jira field names."""
    
    TIMETRACKING = "timetracking"
    REMAINING_ESTIMATE = "remainingEstimate"
    ORIGINAL_ESTIMATE = "originalEstimate"
    REPORTER = "reporter"
    ASSIGNEE = "assignee"
    STATUS = "status"
