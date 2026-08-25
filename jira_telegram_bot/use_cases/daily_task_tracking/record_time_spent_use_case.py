"""Use case for recording time spent on a task."""
from __future__ import annotations

import uuid
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.task_progress_report import (
    UserTaskProgressReport,
)
from jira_telegram_bot.use_cases.interfaces.daily_task_tracking_repository_interface import (
    DailyTaskTrackingRepositoryInterface,
)


class RecordTimeSpentUseCase:
    """Use case for recording time spent on a task."""

    def __init__(
        self,
        tracking_repository: DailyTaskTrackingRepositoryInterface,
    ):
        """Initialize the use case.

        Args:
            tracking_repository: Repository for tracking data
        """
        self.tracking_repository = tracking_repository

    async def execute(
        self,
        issue_key: str,
        jira_username: str,
        telegram_username: str,
        hours_spent: float,
    ) -> UserTaskProgressReport:
        """Record time spent on a task.

        Args:
            issue_key: Jira issue key
            jira_username: User's Jira username
            telegram_username: User's Telegram username
            hours_spent: Hours spent on task

        Returns:
            Created progress report
        """
        try:
            report = UserTaskProgressReport(
                report_id=str(uuid.uuid4()),
                issue_key=issue_key,
                user_jira_username=jira_username,
                user_telegram_username=telegram_username,
                report_date=datetime.now(),
                hours_spent=hours_spent,
            )
            
            await self.tracking_repository.save_progress_report(report)
            
            LOGGER.info(
                f"Recorded {hours_spent} hours for {issue_key} by {jira_username}"
            )
            
            return report
            
        except Exception as e:
            LOGGER.error(f"Error recording time spent: {e}")
            raise
