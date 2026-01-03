"""Use case for requesting subtask creation."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants.persian_messages import (
    PO_SUBTASK_REQUEST,
)
from jira_telegram_bot.entities.daily_task_tracking.task_progress_report import (
    UserTaskProgressReport,
)
from jira_telegram_bot.use_cases.interfaces.daily_task_tracking_repository_interface import (
    DailyTaskTrackingRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.telegram_notifier_interface import (
    TelegramNotifierInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class RequestSubtaskCreationUseCase:
    """Use case for requesting PO to create subtasks."""

    def __init__(
        self,
        tracking_repository: DailyTaskTrackingRepositoryInterface,
        project_info_repository: ProjectInfoRepositoryInterface,
        user_config_repository: UserConfigInterface,
        telegram_notifier: TelegramNotifierInterface,
    ):
        """Initialize the use case.

        Args:
            tracking_repository: Repository for tracking data
            project_info_repository: Repository for project info
            user_config_repository: Repository for user config
            telegram_notifier: Telegram notifier service
        """
        self.tracking_repository = tracking_repository
        self.project_info_repository = project_info_repository
        self.user_config_repository = user_config_repository
        self.telegram_notifier = telegram_notifier

    async def execute(
        self,
        issue_key: str,
        issue_summary: str,
        project_key: str,
        jira_username: str,
        telegram_username: str,
    ) -> UserTaskProgressReport:
        """Request subtask creation from PO.

        Args:
            issue_key: Jira issue key
            issue_summary: Issue summary
            project_key: Project key
            jira_username: User's Jira username
            telegram_username: User's Telegram username

        Returns:
            Progress report
        """
        try:
            po_chat_id = await self._get_po_chat_id(project_key)
            
            po_notified = False
            if po_chat_id:
                message = PO_SUBTASK_REQUEST.format(
                    assignee=telegram_username or jira_username,
                    issue_key=issue_key,
                    summary=issue_summary,
                )
                
                try:
                    await self.telegram_notifier._send_message(
                        po_chat_id,
                        message,
                    )
                    po_notified = True
                    LOGGER.info(f"Notified PO about subtask request for {issue_key}")
                except Exception as e:
                    LOGGER.error(f"Failed to notify PO: {e}")
            
            report = UserTaskProgressReport(
                report_id=str(uuid.uuid4()),
                issue_key=issue_key,
                user_jira_username=jira_username,
                user_telegram_username=telegram_username,
                report_date=datetime.now(),
                subtask_requested=True,
                po_notified=po_notified,
                notes=f"Requested subtask creation for {issue_key}",
            )
            
            await self.tracking_repository.save_progress_report(report)
            
            return report
            
        except Exception as e:
            LOGGER.error(f"Error requesting subtask creation: {e}")
            raise

    async def _get_po_chat_id(self, project_key: str) -> Optional[int]:
        """Get PO's Telegram chat ID for a project.

        Args:
            project_key: Project key

        Returns:
            PO's chat ID if found
        """
        try:
            project_info = await self.project_info_repository.get_project_info(
                project_key
            )
            
            po_jira_username = project_info.get("po_username") or project_info.get(
                "product_owner"
            )
            
            if not po_jira_username:
                LOGGER.warning(f"No PO found in project info for {project_key}")
                return None
            
            po_config = self.user_config_repository.get_user_config_by_jira_username(
                po_jira_username
            )
            
            if po_config and po_config.telegram_user_chat_id:
                return po_config.telegram_user_chat_id
            
            return None
            
        except Exception as e:
            LOGGER.error(f"Error getting PO chat ID: {e}")
            return None
