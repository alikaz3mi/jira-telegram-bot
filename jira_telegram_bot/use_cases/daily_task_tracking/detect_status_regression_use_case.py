"""Use case for detecting status regression (Review -> Backlog)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.task_status_change import (
    TaskStatusChange,
    StatusChangeType,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class DetectStatusRegressionUseCase:
    """Use case for detecting when tasks regress from Review to Backlog."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
    ):
        """Initialize the use case.

        Args:
            task_manager_repository: Repository for task management
        """
        self.task_manager_repository = task_manager_repository

    async def execute(
        self,
        issue_key: str,
        hours_lookback: int = 24,
    ) -> Optional[TaskStatusChange]:
        """Detect status regression for an issue.

        Args:
            issue_key: Jira issue key
            hours_lookback: Hours to look back for changes

        Returns:
            TaskStatusChange if regression detected, None otherwise
        """
        try:
            # Get issue with changelog
            issue = self.task_manager_repository.get_issue(issue_key)
            
            # Check if issue has changelog - some repositories may not support expand parameter
            if not hasattr(issue, "changelog") or not issue.changelog:
                # Try alternative method to get changelog
                try:
                    changelog = self.task_manager_repository.jira.issue(
                        issue_key,
                        expand="changelog"
                    )
                    issue = changelog
                except Exception:
                    LOGGER.debug(f"Could not fetch changelog for {issue_key}")
                    return None
            
            if not hasattr(issue, "changelog"):
                return None
            
            assignee = (
                getattr(issue.fields.assignee, "name", None)
                if issue.fields.assignee
                else None
            )
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_lookback)
            
            for history in issue.changelog.histories:
                change_time_str = history.created.replace("Z", "+00:00") if isinstance(history.created, str) else str(history.created)
                change_time = datetime.fromisoformat(change_time_str)
                
                # Make sure both datetimes are timezone-aware
                if change_time.tzinfo is None:
                    change_time = change_time.replace(tzinfo=timezone.utc)
                
                if change_time < cutoff_time:
                    continue
                
                changed_by = getattr(history.author, "name", "Unknown")
                
                for item in history.items:
                    if item.field == "status":
                        from_status = item.fromString
                        to_status = item.toString
                        
                        if self._is_regression(from_status, to_status):
                            if changed_by != assignee:
                                return TaskStatusChange(
                                    issue_key=issue_key,
                                    from_status=from_status,
                                    to_status=to_status,
                                    changed_by=changed_by,
                                    changed_at=change_time,
                                    change_type=StatusChangeType.REGRESSION,
                                    assignee=assignee,
                                )
            
            return None
            
        except Exception as e:
            LOGGER.error(f"Error detecting status regression for {issue_key}: {e}")
            return None

    def _is_regression(self, from_status: str, to_status: str) -> bool:
        """Check if status change is a regression.

        Args:
            from_status: Previous status
            to_status: New status

        Returns:
            True if regression detected
        """
        from_lower = from_status.lower()
        to_lower = to_status.lower()
        
        review_states = ["review", "in review", "code review", "qa", "testing"]
        backlog_states = ["backlog", "to do", "open"]
        
        is_from_review = any(state in from_lower for state in review_states)
        is_to_backlog = any(state in to_lower for state in backlog_states)
        
        return is_from_review and is_to_backlog
