"""Use case for recording worklog to Jira."""
from __future__ import annotations

import uuid
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.task_progress_report import (
    UserTaskProgressReport,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_entry import (
    WorklogEntry,
)
from jira_telegram_bot.use_cases.interfaces.daily_task_tracking_repository_interface import (
    DailyTaskTrackingRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class RecordWorklogUseCase:
    """Use case for adding worklog to Jira and tracking locally."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        tracking_repository: DailyTaskTrackingRepositoryInterface,
    ):
        """Initialize the use case.

        Args:
            task_manager_repository: Repository for task management
            tracking_repository: Repository for tracking data
        """
        self.task_manager_repository = task_manager_repository
        self.tracking_repository = tracking_repository

    async def execute(
        self,
        issue_key: str,
        jira_username: str,
        telegram_username: str,
        hours: float,
        comment: str = None,
    ) -> UserTaskProgressReport:
        """Add worklog to Jira and record locally.

        Args:
            issue_key: Jira issue key
            jira_username: User's Jira username
            telegram_username: User's Telegram username
            hours: Hours to log
            comment: Optional worklog comment

        Returns:
            Progress report with worklog info
        """
        try:
            time_spent = f"{int(hours)}h"
            if hours != int(hours):
                minutes = int((hours - int(hours)) * 60)
                time_spent = f"{int(hours)}h {minutes}m"
            
            worklog_comment = comment or "Logged via daily task tracker"
            
            try:
                worklog = self.task_manager_repository.jira.add_worklog(
                    issue=issue_key,
                    timeSpent=time_spent,
                    comment=worklog_comment,
                )
                worklog_added = True
                LOGGER.info(f"Added worklog to Jira for {issue_key}: {time_spent}")
            except Exception as e:
                LOGGER.error(f"Failed to add worklog to Jira: {e}")
                worklog_added = False
            
            report = UserTaskProgressReport(
                report_id=str(uuid.uuid4()),
                issue_key=issue_key,
                user_jira_username=jira_username,
                user_telegram_username=telegram_username,
                report_date=datetime.now(),
                hours_spent=hours,
                worklog_added=worklog_added,
                notes=f"Worklog: {time_spent}",
            )
            
            await self.tracking_repository.save_progress_report(report)
            
            return report
            
        except Exception as e:
            LOGGER.error(f"Error recording worklog: {e}")
            raise
