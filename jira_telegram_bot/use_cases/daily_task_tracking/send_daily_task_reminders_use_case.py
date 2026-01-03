"""Main use case for sending daily task reminders."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants.persian_messages import (
    STATUS_REGRESSION_MESSAGE,
    DAILY_CHECK_START,
    DAILY_CHECK_COMPLETE,
    TASK_NOT_STARTED,
    HOURS_TODAY,
    WORKLOG_MISSING,
    REASON_TEXT,
    TASK_HEADER_WITH_DATES,
    TASK_HEADER,
    TASK_DESCRIPTION,
)
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
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)
from jira_telegram_bot.frameworks.telegram.daily_task_queue_manager import (
    DailyTaskQueueManager,
)
from telegram import Bot


class SendDailyTaskRemindersUseCase:
    """Orchestrator use case for sending daily task reminders to all users."""

    def __init__(
        self,
        get_user_daily_tasks_use_case: GetUserDailyTasksUseCase,
        detect_status_regression_use_case: DetectStatusRegressionUseCase,
        user_config_repository: UserConfigInterface,
        telegram_notifier: TelegramNotifierInterface,
        task_manager_repository: TaskManagerRepositoryInterface,
        project_info_repository: ProjectInfoRepositoryInterface,
        daily_task_tracking_handler: Any,
        telegram_token: str,
        queue_manager: DailyTaskQueueManager,
    ):
        """Initialize the use case.

        Args:
            get_user_daily_tasks_use_case: Use case for getting user tasks
            detect_status_regression_use_case: Use case for detecting regressions
            user_config_repository: Repository for user config
            telegram_notifier: Telegram notifier service
            task_manager_repository: Repository for task management
            project_info_repository: Repository for project info
            daily_task_tracking_handler: Handler for telegram keyboards
            telegram_token: Telegram bot token
            queue_manager: Task queue manager
        """
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.detect_regression = detect_status_regression_use_case
        self.user_config_repository = user_config_repository
        self.telegram_notifier = telegram_notifier
        self.task_manager_repository = task_manager_repository
        self.project_info_repository = project_info_repository
        self.handler = daily_task_tracking_handler
        self.telegram_token = telegram_token
        self.queue_manager = queue_manager
        self.bot = Bot(token=telegram_token)
        self.welcome_sent_today = {}  # Track welcome messages per day per user
        
        # Set task sender callable
        self.handler.task_sender = self._send_task_or_complete

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
                # FOR TESTING: Only process alikaz3mi
                if user_config.telegram_username != "alikaz3mi":
                    LOGGER.debug(
                        f"Skipping {telegram_username}: Testing mode (only alikaz3mi)"
                    )
                    continue
                    
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
        
        # Group tasks by project
        projects = {}
        for task in tasks:
            if task.project_key not in projects:
                projects[task.project_key] = 0
            projects[task.project_key] += 1
        
        project_summary = ", ".join([f"{key}: {count}" for key, count in projects.items()])
        
        # Send summary
        await self.telegram_notifier._send_message(
            chat_id,
            f"📋 شما {len(tasks)} تسک دارید که نیاز به بررسی دارند\n"
            f"📦 پروژه‌ها: {project_summary}\n\n"
            f"تسک‌ها یکی یکی برای شما ارسال می‌شوند. لطفاً برای هر تسک پاسخ دهید."
        )
        
        # Create queue for this user
        self.queue_manager.create_queue(chat_id, tasks)
        
        # Send first task
        await self._send_next_task_in_queue(chat_id)
        
        stats["reminders_sent"] += 1

    async def _send_welcome_message(self, chat_id: int) -> None:
        """Send welcome message to user.

        Args:
            chat_id: User's chat ID
        """
        try:
            await self.telegram_notifier._send_message(
                chat_id,
                DAILY_CHECK_START,
            )
        except Exception as e:
            LOGGER.error(f"Error sending welcome message: {e}")

    async def _send_next_task_in_queue(self, chat_id: int) -> None:
        """Send next task from queue to user.
        
        Args:
            chat_id: User's chat ID
        """
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            LOGGER.warning(f"No queue found for chat_id {chat_id}")
            return
        
        task = queue.get_current()
        if not task:
            LOGGER.warning(f"No current task in queue for chat_id {chat_id}")
            return
        
        LOGGER.info(f"Sending task {task.issue_key} to chat_id {chat_id} (index {queue.current_index})")
        
        try:
            # Show progress
            progress = queue.get_progress()
            await self.telegram_notifier._send_message(
                chat_id,
                f"━━━━━━━━━━━━━━━━━━\n📌 تسک {progress}\n━━━━━━━━━━━━━━━━━━"
            )
            
            # Check for status regression
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
            
            # Send the task reminder with keyboard
            await self._send_task_reminder(chat_id, task)
            LOGGER.info(f"Task {task.issue_key} sent successfully")
            
        except Exception as e:
            LOGGER.error(f"Error sending task {task.issue_key}: {e}", exc_info=True)
            # Don't automatically skip - let user handle it
            raise

    async def _send_task_or_complete(self, chat_id: int) -> None:
        """Send next task or completion message.
        
        This is called by handler after user response.
        
        Args:
            chat_id: User's chat ID
        """
        LOGGER.info(f"_send_task_or_complete called for chat_id {chat_id}")
        
        # Move to next task first
        has_next = self.queue_manager.move_to_next(chat_id)
        LOGGER.info(f"After move_to_next: has_next={has_next}")
        
        if not has_next:
            # No more tasks
            LOGGER.info(f"No more tasks, sending completion message")
            await self._send_completion_message(chat_id)
            self.queue_manager.clear_queue(chat_id)
        else:
            # Send next task
            LOGGER.info(f"Sending next task in queue")
            await self._send_next_task_in_queue(chat_id)


    async def _send_completion_message(self, chat_id: int) -> None:
        """Send completion message to user.

        Args:
            chat_id: User's chat ID
        """
        try:
            await self.telegram_notifier._send_message(
                chat_id,
                DAILY_CHECK_COMPLETE,
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
            message = await self._format_task_header(task)
            keyboard = None
            
            if task.check_status == TaskCheckStatus.SHOULD_BE_STARTED:
                message += f"\n{TASK_NOT_STARTED}"
                keyboard = self.handler.create_delay_reason_keyboard()
            elif task.check_status == TaskCheckStatus.IN_PROGRESS:
                message += f"\n{HOURS_TODAY}"
                keyboard = self.handler.create_hours_keyboard(prefix="hours")
            elif task.check_status == TaskCheckStatus.NEEDS_WORKLOG:
                message += f"\n{WORKLOG_MISSING}"
                keyboard = self.handler.create_hours_keyboard(prefix="worklog")
            else:
                return False
            
            if keyboard:
                # Use Telegram bot to send with keyboard
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    reply_markup=keyboard,
                )
            else:
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
                reason_text = REASON_TEXT.format(
                    reason=regression.reason
                )
            
            message = STATUS_REGRESSION_MESSAGE.format(
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

    async def _format_task_header(self, task: DailyTaskCheck) -> str:
        """Format task header message.

        Args:
            task: Task check

        Returns:
            Formatted header string
        """
        # Build Jira URL using repository
        issue_url = self.task_manager_repository.get_issue_url_by_key(task.issue_key)
        
        # Get project name from projects_info.json
        project_name = task.project_key
        try:
            project_info = await self.project_info_repository.get_project_info(task.project_key)
            if project_info and hasattr(project_info, 'project_info'):
                # Extract first keyword or use key
                if hasattr(project_info.project_info, 'keywords') and project_info.project_info.keywords:
                    project_name = project_info.project_info.keywords[0]
                elif hasattr(project_info.project_info, 'description'):
                    # Use first few words of description
                    words = project_info.project_info.description.split()[:3]
                    project_name = " ".join(words)
        except Exception as e:
            LOGGER.debug(f"Could not get project name for {task.project_key}: {e}")
        
        # Format header with or without dates
        if task.target_start and task.target_end:
            header = TASK_HEADER_WITH_DATES.format(
                issue_key=task.issue_key,
                issue_url=issue_url,
                summary=task.summary,
                status=task.status,
                sprint_name=task.sprint_name or "N/A",
                target_start=task.target_start.strftime("%Y-%m-%d"),
                target_end=task.target_end.strftime("%Y-%m-%d"),
            )
        else:
            header = TASK_HEADER.format(
                issue_key=task.issue_key,
                issue_url=issue_url,
                summary=task.summary,
                status=task.status,
                sprint_name=task.sprint_name or "N/A",
            )
        
        # Add project name
        header += f"\n📁 پروژه: {project_name}\n"
        
        # Add description if available (first 20 words)
        if task.description:
            words = task.description.split()[:20]
            description_preview = " ".join(words)
            if len(task.description.split()) > 20:
                description_preview += "..."
            header += TASK_DESCRIPTION.format(description=description_preview)
        
        return header
