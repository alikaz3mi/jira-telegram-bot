"""Deadline service for team evaluation."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot, ChangeLogEvent
from jira_telegram_bot.entities.constants import (
    DONE_STATUSES,
    REVIEW_STATUSES,
    PENALTY_COEFFICIENT_MAX,
    PENALTY_COEFFICIENT_MIN,
    PENALTY_COEFFICIENT_TASK_THRESHOLD,
    PRIORITY_WEIGHT_HIGHEST,
    PRIORITY_WEIGHT_HIGH,
    PRIORITY_WEIGHT_OTHERS,
    UNDELIVERED_TASK_DELAY_DAYS
)


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
        
        now = datetime.now(timezone.utc)
        
        def sort_key(issue: IssueSnapshot):
            """Sort key: overdue Highest tasks first, then by deadline and priority."""
            due_date = issue.due_date if issue.due_date else datetime.max.replace(tzinfo=None)
            due_date_normalized = DeadlineService._normalize_datetime(due_date) if issue.due_date else due_date
            priority = priority_order.get(issue.priority, 6)
            
            # Check if task is overdue
            is_overdue = due_date_normalized < now if issue.due_date else False
            
            # Sort order:
            # 1. Overdue status (overdue first)
            # 2. Priority (for overdue tasks, Highest comes first)
            # 3. Due date (earlier deadline first)
            # 4. Issue key (for stability)
            return (
                not is_overdue,  # False (overdue) comes before True (not overdue)
                priority if is_overdue else 999,  # Priority matters only for overdue
                due_date_normalized,
                priority if not is_overdue else 999,  # Priority for non-overdue
                issue.key
            )
        
        sorted_issues = sorted(issues, key=sort_key)
        
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
        grace_period_days: int = 2,
        sprint_end_date: Optional[datetime] = None
    ) -> float:
        """Calculate total deadline penalty/bonus based on individual task delivery times.
        
        Penalty/bonus per day is calculated dynamically based on task count:
        - Few tasks (1-2): High penalty coefficient (PENALTY_COEFFICIENT_MAX = 15 points/day)
        - Many tasks (10+): Lower penalty coefficient (PENALTY_COEFFICIENT_MIN = 5 points/day)
        - Formula: base_coefficient = MAX - (range × min(task_count - 1, threshold) / threshold)
          Clamped between PENALTY_COEFFICIENT_MIN and PENALTY_COEFFICIENT_MAX
        
        This is then multiplied by priority weight:
        - Highest: PRIORITY_WEIGHT_HIGHEST (1.0x)
        - High: PRIORITY_WEIGHT_HIGH (0.6x)
        - Others: PRIORITY_WEIGHT_OTHERS (0.2x)
        
        Penalties (positive values):
        - Late delivery after grace period
        - For undelivered tasks: assumed delivered 1 day after sprint end
          
        Bonuses (negative values = reducing penalty):
        - Early delivery (same rate as penalties)
        
        Args:
            issues: List of issues (both delivered and undelivered)
            changelogs: Dictionary of changelog events per issue
            grace_period_days: Number of days grace period before penalties apply (for late delivery)
            sprint_end_date: Sprint end date (used for undelivered tasks)
            
        Returns:
            Total penalty score (positive = penalty, negative = bonus)
        """
        total_penalty = 0.0
        
        # Calculate dynamic penalty coefficient based on task count
        task_count = len(issues)
        if task_count == 0:
            return 0.0
        
        # Formula: starts at PENALTY_COEFFICIENT_MAX for 1 task, decreases to PENALTY_COEFFICIENT_MIN for 10+ tasks
        # For 1 task: 15 - (10 * 0 / 9) = 15
        # For 10 tasks: 15 - (10 * 9 / 9) = 5
        coefficient_range = PENALTY_COEFFICIENT_MAX - PENALTY_COEFFICIENT_MIN
        base_coefficient = PENALTY_COEFFICIENT_MAX - (coefficient_range * min(task_count - 1, PENALTY_COEFFICIENT_TASK_THRESHOLD) / PENALTY_COEFFICIENT_TASK_THRESHOLD)
        base_coefficient = max(PENALTY_COEFFICIENT_MIN, min(PENALTY_COEFFICIENT_MAX, base_coefficient))
        
        for issue in issues:
            if not issue.due_date:
                continue
            
            # Try to find actual delivery time
            delivery_time = DeadlineService._find_delivery_time(issue.key, changelogs)
            
            # If not delivered and sprint_end_date provided, assume delivery after sprint end
            if not delivery_time and sprint_end_date:
                # Task not delivered: assume delivered UNDELIVERED_TASK_DELAY_DAYS after sprint end
                delivery_time = sprint_end_date + timedelta(days=UNDELIVERED_TASK_DELAY_DAYS)
                delivery_time = DeadlineService._normalize_datetime(delivery_time)
            
            if not delivery_time:
                # Skip if no delivery time and no sprint_end_date
                continue
            
            due_date_normalized = DeadlineService._normalize_datetime(issue.due_date)
            delivery_time_normalized = DeadlineService._normalize_datetime(delivery_time)
            
            delta_days = (delivery_time_normalized - due_date_normalized).total_seconds() / (24 * 3600)
            
            # Priority weight multiplier
            if issue.priority == "Highest":
                priority_weight = PRIORITY_WEIGHT_HIGHEST
            elif issue.priority == "High":
                priority_weight = PRIORITY_WEIGHT_HIGH
            else:
                priority_weight = PRIORITY_WEIGHT_OTHERS
            
            points_per_day = base_coefficient * priority_weight
            
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
        """Find when an issue was last moved to Review status.
        
        Args:
            issue_key: The issue key to check
            changelogs: Dictionary of changelog events per issue
            
        Returns:
            Datetime of the last (most recent) transition to Review, or None if not found
        """
        issue_changelogs = changelogs.get(issue_key, [])
        
        last_review_time = None
        
        # Find the most recent transition to Review status by comparing timestamps
        for changelog in issue_changelogs:
            if (changelog.field.lower() == "status" and 
                changelog.to_status and 
                changelog.to_status in REVIEW_STATUSES):
                if last_review_time is None or changelog.changed_at > last_review_time:
                    last_review_time = changelog.changed_at
        
        return last_review_time

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
        
        # Find the most recent Done time by comparing timestamps
        done_time = None
        for changelog in issue_changelogs:
            if (changelog.field.lower() == "status" and 
                changelog.to_status and 
                changelog.to_status in DONE_STATUSES):
                if done_time is None or changelog.changed_at > done_time:
                    done_time = changelog.changed_at
        
        if not done_time:
            return None
        
        # Find the last Review time using helper method
        review_time = DeadlineService._find_review_time(issue_key, changelogs)
        
        # If both Review and Done exist and happened on the same day, use Review time
        if review_time:
            review_date = review_time.date()
            done_date = done_time.date()
            
            if review_date == done_date:
                return review_time
        
        return done_time
