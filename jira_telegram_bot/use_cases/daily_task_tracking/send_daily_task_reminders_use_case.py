"""Main use case for sending daily task reminders."""
from __future__ import annotations

from typing import Dict, List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants import persian_messages
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.detect_status_regression_use_case import (
    DetectStatusRegressionUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    GetUserDailyTasksUseCase,
)
from jira_telegram_bot.use_cases.interfaces.telegram_notifier_interface import (
    TelegramNotifierInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SendDailyTaskRemindersUseCase:
    """Orchestrator use case for sending daily task reminders to all users."""

    def __init__(
        self,
        get_user_daily_tasks_use_case: GetUserDailyTasksUseCase,
        detect_status_regression_use_case: DetectStatusRegressionUseCase,
        user_config_repository: UserConfigInterface,
        telegram_notifier: TelegramNotifierInterface,
    ):
        """Initialize the use case.

        Args:
            get_user_daily_tasks_use_case: Use case for getting user tasks
            detect_status_regression_use_case: Use case for detecting regressions
            user_config_repository: Repository for user config
            telegram_notifier: Telegram notifier service
        """
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.detect_regression = detect_status_regression_use_case
        self.user_config_repository = user_config_repository
        self.telegram_notifier = telegram_notifier

    async def execute(self) -> Dict[str, int]:
        """Send daily task reminders to all users.

        Returns:
            Statistics dictionary with counts
        """
        stats = {
            "users_processed": 0,
            "tasks_checked": 0,
            "reminders_sent": 0,
            "regressions_found": 0,
            "errors": 0,
        }
        
        try:
            all_users = self.user_config_repository.get_all_user_configs()
            
            for telegram_username, user_config in all_users.items():
                if not user_config.jira_username:
                    continue
                
                if not user_config.telegram_user_chat_id:
                    LOGGER.debug(
                        f"Skipping {telegram_username}: no chat ID"
                    )
                    continue
                
                try:
                    await self._process_user(
                        user_config.jira_username,
                        telegram_username,
                        user_config.telegram_user_chat_id,
                        stats,
                    )
                    stats["users_processed"] += 1
                    
                except Exception as e:
                    LOGGER.error(
                        f"Error processing user {telegram_username}: {e}"
                    )
                    stats["errors"] += 1
            
            LOGGER.info(
                f"Daily task reminders complete: {stats}"
            )
            
            return stats
            
        except Exception as e:
            LOGGER.error(f"Error in send daily task reminders: {e}")
            raise

    async def _process_user(
        self,
        jira_username: str,
        telegram_username: str,
        chat_id: int,
        stats: Dict[str, int],
    ) -> None:
        """Process daily tasks for a single user.

        Args:
            jira_username: User's Jira username
            telegram_username: User's Telegram username
            chat_id: User's Telegram chat ID
            stats: Statistics dictionary to update
        """
        tasks = await self.get_user_daily_tasks.execute(jira_username)
        
        stats["tasks_checked"] += len(tasks)
        
        if not tasks:
            LOGGER.debug(f"No tasks needing attention for {jira_username}")
            return
        
        await self._send_welcome_message(chat_id)
        
        for task in tasks:
            try:
                regression = await self.detect_regression.execute(
                    task.issue_key,
                    hours_lookback=24,
                )
                
                if regression:
                    await self._send_regression_notification(
                        chat_id,
                        task,
                        regression,
                    )
                    stats["regressions_found"] += 1
                
                sent = await self._send_task_reminder(
                    chat_id,
                    task,
                )
                
                if sent:
                    stats["reminders_sent"] += 1
                    
            except Exception as e:
                LOGGER.error(
                    f"Error processing task {task.issue_key} for {jira_username}: {e}"
                )
        
        await self._send_completion_message(chat_id)

    async def _send_welcome_message(self, chat_id: int) -> None:
        """Send welcome message to user.

        Args:
            chat_id: User's chat ID
        """
        try:
            await self.telegram_notifier._send_message(
                chat_id,
                persian_messages.DAILY_CHECK_START,
            )
        except Exception as e:
            LOGGER.error(f"Error sending welcome message: {e}")

    async def _send_completion_message(self, chat_id: int) -> None:
        """Send completion message to user.

        Args:
            chat_id: User's chat ID
        """
        try:
            await self.telegram_notifier._send_message(
                chat_id,
                persian_messages.DAILY_CHECK_COMPLETE,
            )
        except Exception as e:
            LOGGER.error(f"Error sending completion message: {e}")

    async def _send_task_reminder(
        self,
        chat_id: int,
        task: DailyTaskCheck,
    ) -> bool:
        """Send task reminder to user.

        Args:
            chat_id: User's chat ID
            task: Task check to send

        Returns:
            True if sent successfully
        """
        try:
            if task.check_status == TaskCheckStatus.SHOULD_BE_STARTED:
                message = self._format_task_header(task)
                message += f"\n{persian_messages.TASK_NOT_STARTED}"
            elif task.check_status == TaskCheckStatus.IN_PROGRESS:
                message = self._format_task_header(task)
                message += f"\n{persian_messages.HOURS_TODAY}"
            elif task.check_status == TaskCheckStatus.NEEDS_WORKLOG:
                message = self._format_task_header(task)
                message += f"\n{persian_messages.WORKLOG_MISSING}"
            else:
                return False
            
            await self.telegram_notifier._send_message(chat_id, message)
            return True
            
        except Exception as e:
            LOGGER.error(f"Error sending task reminder: {e}")
            return False

    async def _send_regression_notification(
        self,
        chat_id: int,
        task: DailyTaskCheck,
        regression,
    ) -> None:
        """Send status regression notification.

        Args:
            chat_id: User's chat ID
            task: Task check
            regression: TaskStatusChange object
        """
        try:
            reason_text = ""
            if regression.reason:
                reason_text = persian_messages.REASON_TEXT.format(
                    reason=regression.reason
                )
            
            message = persian_messages.STATUS_REGRESSION_MESSAGE.format(
                issue_key=task.issue_key,
                summary=task.summary,
                from_status=regression.from_status,
                to_status=regression.to_status,
                changed_by=regression.changed_by,
                changed_at=regression.changed_at.strftime("%Y-%m-%d %H:%M"),
                reason_text=reason_text,
            )
            
            await self.telegram_notifier._send_message(chat_id, message)
            
        except Exception as e:
            LOGGER.error(f"Error sending regression notification: {e}")

    def _format_task_header(self, task: DailyTaskCheck) -> str:
        """Format task header message.

        Args:
            task: Task check

        Returns:
            Formatted header string
        """
        if task.target_start and task.target_end:
            return persian_messages.TASK_HEADER_WITH_DATES.format(
                issue_key=task.issue_key,
                summary=task.summary,
                status=task.status,
                sprint_name=task.sprint_name or "N/A",
                target_start=task.target_start.strftime("%Y-%m-%d"),
                target_end=task.target_end.strftime("%Y-%m-%d"),
            )
        else:
            return persian_messages.TASK_HEADER.format(
                issue_key=task.issue_key,
                summary=task.summary,
                status=task.status,
                sprint_name=task.sprint_name or "N/A",
            )
