"""Use case for recording delay reason."""
from __future__ import annotations

import uuid
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    DelayReason,
)
from jira_telegram_bot.entities.daily_task_tracking.task_progress_report import (
    UserTaskProgressReport,
)
from jira_telegram_bot.use_cases.interfaces.daily_task_tracking_repository_interface import (
    DailyTaskTrackingRepositoryInterface,
)


class RecordDelayReasonUseCase:
    """Use case for recording why a task hasn't been started."""

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
        delay_reason: DelayReason,
        delay_reason_text: str = None,
    ) -> UserTaskProgressReport:
        """Record delay reason for a task.

        Args:
            issue_key: Jira issue key
            jira_username: User's Jira username
            telegram_username: User's Telegram username
            delay_reason: Reason for delay
            delay_reason_text: Custom delay reason text

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
                delay_reason=delay_reason,
                delay_reason_text=delay_reason_text,
            )
            
            await self.tracking_repository.save_progress_report(report)
            
            LOGGER.info(
                f"Recorded delay reason for {issue_key} by {jira_username}: {delay_reason}"
            )
            
            return report
            
        except Exception as e:
            LOGGER.error(f"Error recording delay reason: {e}")
            raise
