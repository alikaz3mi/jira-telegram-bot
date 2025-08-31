"""Deadline service for team evaluation."""

from datetime import datetime, timezone
from typing import List, Optional, Dict

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot, ChangeLogEvent
from jira_telegram_bot.entities.constants import DONE_STATUSES


class DeadlineService:
    """Service for deadline-related calculations."""

    @staticmethod
    def average_deadline_delta_hours(
        issues: List[IssueSnapshot], 
        changelogs: Dict[str, List[ChangeLogEvent]]
    ) -> Optional[float]:
        """Calculate average deadline delivery delta in hours.
        
        Args:
            issues: List of delivered issues
            changelogs: Dictionary of changelog events per issue
            
        Returns:
            Average delta in hours, or None if no due dates
        """
        deltas = []
        
        for issue in issues:
            if not issue.due_date:
                continue
                
            # Find when the issue was moved to Done/Closed status
            delivery_time = DeadlineService._find_delivery_time(issue.key, changelogs)
            
            if delivery_time:
                # Ensure both datetimes have consistent timezone handling
                due_date_normalized = DeadlineService._normalize_datetime(issue.due_date)
                delivery_time_normalized = DeadlineService._normalize_datetime(delivery_time)
                
                # Calculate delta in hours (positive = late, negative = early)
                delta = (delivery_time_normalized - due_date_normalized).total_seconds() / 3600
                deltas.append(delta)
        
        if not deltas:
            return None
        
        return sum(deltas) / len(deltas)

    @staticmethod
    def average_deadline_delta_days(
        issues: List[IssueSnapshot], 
        changelogs: Dict[str, List[ChangeLogEvent]]
    ) -> Optional[float]:
        """Calculate average deadline delivery delta in days.
        
        Args:
            issues: List of delivered issues
            changelogs: Dictionary of changelog events per issue
            
        Returns:
            Average delta in days, or None if no due dates
        """
        deltas = []
        
        for issue in issues:
            if not issue.due_date:
                continue
                
            # Find when the issue was moved to Done/Closed status
            delivery_time = DeadlineService._find_delivery_time(issue.key, changelogs)
            
            if delivery_time:
                # Ensure both datetimes have consistent timezone handling
                due_date_normalized = DeadlineService._normalize_datetime(issue.due_date)
                delivery_time_normalized = DeadlineService._normalize_datetime(delivery_time)
                
                # Calculate delta in days (positive = late, negative = early)
                delta_days = (delivery_time_normalized - due_date_normalized).total_seconds() / (24 * 3600)
                deltas.append(delta_days)
        
        if not deltas:
            return None
        
        return sum(deltas) / len(deltas)

    @staticmethod
    def _normalize_datetime(dt: datetime) -> datetime:
        """Normalize datetime to ensure consistent timezone handling.
        
        Args:
            dt: Input datetime (may be naive or aware)
            
        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            # If naive, assume it's in UTC
            return dt.replace(tzinfo=timezone.utc)
        else:
            # If already aware, convert to UTC
            return dt.astimezone(timezone.utc)

    @staticmethod
    def _find_delivery_time(issue_key: str, changelogs: Dict[str, List[ChangeLogEvent]]) -> Optional[datetime]:
        """Find when an issue was moved to Done/Closed status.
        
        Args:
            issue_key: The issue key to check
            changelogs: Dictionary of changelog events per issue
            
        Returns:
            Datetime when issue was moved to Done/Closed, or None if not found
        """
        issue_changelogs = changelogs.get(issue_key, [])
        
        # Look for the first transition to a Done status
        for changelog in issue_changelogs:
            if (changelog.field.lower() == "status" and 
                changelog.to_status and 
                changelog.to_status in DONE_STATUSES):
                return changelog.changed_at
        
        return None
