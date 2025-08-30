"""Deadline service for team evaluation."""

from datetime import datetime
from typing import List, Optional

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot


class DeadlineService:
    """Service for deadline-related calculations."""

    @staticmethod
    def average_deadline_delta_hours(issues: List[IssueSnapshot]) -> Optional[float]:
        """Calculate average deadline delivery delta in hours.
        
        Args:
            issues: List of delivered issues
            
        Returns:
            Average delta in hours, or None if no due dates
        """
        deltas = []
        
        for issue in issues:
            if issue.due_date and issue.resolution_date:
                # Calculate delta in hours
                delta = (issue.resolution_date - issue.due_date).total_seconds() / 3600
                deltas.append(delta)
        
        if not deltas:
            return None
        
        return sum(deltas) / len(deltas)
