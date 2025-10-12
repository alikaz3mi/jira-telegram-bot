"""Deadline service for team evaluation."""

from datetime import datetime, timezone
from typing import List, Optional, Dict

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot, ChangeLogEvent
from jira_telegram_bot.entities.constants import DONE_STATUSES, REVIEW_STATUSES


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
    def select_tasks_for_evaluation(
        issues: List[IssueSnapshot],
        max_hours: float
    ) -> tuple[List[IssueSnapshot], List[IssueSnapshot]]:
        """Select which tasks should be evaluated when total exceeds capacity.
        
        When a developer has more tasks than they can reasonably complete,
        select tasks based on deadline proximity and priority.
        
        Args:
            issues: All issues assigned to developer
            max_hours: Maximum reasonable hours (e.g., DEFAULT_WEEKLY_HOURS)
            
        Returns:
            Tuple of (tasks_for_evaluation, extra_completed_tasks)
        """
        total_estimated_hours = sum(issue.time_estimate_hours or 0.0 for issue in issues)
        
        if total_estimated_hours <= max_hours:
            return issues, []
        
        priority_order = {
            "Highest": 1,
            "High": 2,
            "Medium": 3,
            "Low": 4,
            "Lowest": 5,
            None: 6
        }
        
        sorted_issues = sorted(
            issues,
            key=lambda x: (
                priority_order.get(x.priority, 6),
                x.due_date if x.due_date else datetime.max.replace(tzinfo=None),
                x.key
            )
        )
        
        selected_for_eval = []
        extra_tasks = []
        cumulative_hours = 0.0
        
        for issue in sorted_issues:
            estimated_hours = issue.time_estimate_hours or 0.0
            
            if cumulative_hours < max_hours:
                selected_for_eval.append(issue)
                cumulative_hours += estimated_hours
            else:
                extra_tasks.append(issue)
        
        return selected_for_eval, extra_tasks

    @staticmethod
    def calculate_per_task_deadline_penalties(
        issues: List[IssueSnapshot],
        changelogs: Dict[str, List[ChangeLogEvent]],
        grace_period_days: int = 2
    ) -> float:
        """Calculate total deadline penalty/bonus based on individual task delivery times.
        
        Penalties (positive values):
        - Late delivery after grace period: penalty per day based on priority
          * Highest: -10 points per day
          * High: -5 points per day  
          * Others: -2 points per day
          
        Bonuses (negative values = reducing penalty):
        - Early delivery: bonus per day based on priority
          * Highest: +10 points per day
          * High: +5 points per day
          * Others: +2 points per day
        
        Args:
            issues: List of delivered issues
            changelogs: Dictionary of changelog events per issue
            grace_period_days: Number of days grace period before penalties apply (for late delivery)
            
        Returns:
            Total penalty score (positive = penalty, negative = bonus)
        """
        total_penalty = 0.0
        
        for issue in issues:
            if not issue.due_date:
                continue
            
            delivery_time = DeadlineService._find_delivery_time(issue.key, changelogs)
            if not delivery_time:
                continue
            
            due_date_normalized = DeadlineService._normalize_datetime(issue.due_date)
            delivery_time_normalized = DeadlineService._normalize_datetime(delivery_time)
            
            delta_days = (delivery_time_normalized - due_date_normalized).total_seconds() / (24 * 3600)
            
            if issue.priority == "Highest":
                points_per_day = 5
            elif issue.priority == "High":
                points_per_day = 3
            else:
                points_per_day = 1
            
            if delta_days > grace_period_days:
                days_late = delta_days - grace_period_days
                task_penalty = days_late * points_per_day
                total_penalty += task_penalty
            elif delta_days < 0:
                days_early = abs(delta_days)
                task_bonus = days_early * points_per_day
                total_penalty -= task_bonus
        
        return total_penalty

    @staticmethod
    def _find_review_time(issue_key: str, changelogs: Dict[str, List[ChangeLogEvent]]) -> Optional[datetime]:
        """Find when an issue was moved to Review status.
        
        Args:
            issue_key: The issue key to check
            changelogs: Dictionary of changelog events per issue
            
        Returns:
            Datetime when issue was moved to Review, or None if not found
        """
        issue_changelogs = changelogs.get(issue_key, [])
        
        for changelog in issue_changelogs:
            if (changelog.field.lower() == "status" and 
                changelog.to_status and 
                changelog.to_status in REVIEW_STATUSES):
                return changelog.changed_at
        
        return None

    @staticmethod
    def _find_delivery_time(issue_key: str, changelogs: Dict[str, List[ChangeLogEvent]]) -> Optional[datetime]:
        """Find when an issue was moved to Done/Closed status.
        
        If the issue moved to Review and then to Done on the same day,
        returns the Review time (more fair as developer's work was done).
        
        Args:
            issue_key: The issue key to check
            changelogs: Dictionary of changelog events per issue
            
        Returns:
            Datetime when issue was effectively delivered, or None if not found
        """
        issue_changelogs = changelogs.get(issue_key, [])
        
        done_time = None
        review_time = None
        
        # Find both Review and Done times
        for changelog in issue_changelogs:
            if changelog.field.lower() == "status" and changelog.to_status:
                if changelog.to_status in REVIEW_STATUSES and not review_time:
                    review_time = changelog.changed_at
                elif changelog.to_status in DONE_STATUSES and not done_time:
                    done_time = changelog.changed_at
        
        if not done_time:
            return None
        
        # If both Review and Done exist and happened on the same day, use Review time
        if review_time and done_time:
            review_date = review_time.date()
            done_date = done_time.date()
            
            if review_date == done_date:
                return review_time
        
        return done_time
