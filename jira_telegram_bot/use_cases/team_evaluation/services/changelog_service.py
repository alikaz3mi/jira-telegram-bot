"""Changelog service for team evaluation."""

from typing import List

from jira_telegram_bot.entities.team_evaluation import ChangeLogEvent
from jira_telegram_bot.entities.constants import REVIEW_STATUSES, BACKLOG_STATUSES


class ChangelogService:
    """Service for analyzing changelog events."""

    @staticmethod
    def count_review_regressions(events: List[ChangeLogEvent]) -> int:
        """Count transitions from review back to backlog/in-progress.
        
        Args:
            events: List of changelog events
            
        Returns:
            Number of review regression transitions
        """
        regression_count = 0
        
        for event in events:
            if (event.field.lower() == "status" and
                event.from_status in REVIEW_STATUSES and
                event.to_status in BACKLOG_STATUSES):
                regression_count += 1
        
        return regression_count
