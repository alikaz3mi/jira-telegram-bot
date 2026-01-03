"""Telegram handler for daily task tracking with Persian interface."""
from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, filters

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants import persian_messages
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    DelayReason,
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_delay_reason_use_case import (
    RecordDelayReasonUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_time_spent_use_case import (
    RecordTimeSpentUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_worklog_use_case import (
    RecordWorklogUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.request_subtask_creation_use_case import (
    RequestSubtaskCreationUseCase,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.frameworks.telegram.daily_task_queue_manager import (
    DailyTaskQueueManager,
)

if TYPE_CHECKING:
    from jira_telegram_bot.use_cases.daily_task_tracking.send_daily_task_reminders_use_case import (
        SendDailyTaskRemindersUseCase,
    )


class DailyTaskTrackingHandler:
    """Handler for daily task tracking conversations."""

    WAITING_CUSTOM_HOURS = "waiting_custom_hours"
    WAITING_CUSTOM_DELAY = "waiting_custom_delay"

    def __init__(
        self,
        record_delay_reason_use_case: RecordDelayReasonUseCase,
        record_time_spent_use_case: RecordTimeSpentUseCase,
        record_worklog_use_case: RecordWorklogUseCase,
        request_subtask_creation_use_case: RequestSubtaskCreationUseCase,
        user_config_repository: UserConfigInterface,
        queue_manager: DailyTaskQueueManager,
    ):
        """Initialize the handler.

        Args:
            record_delay_reason_use_case: Use case for recording delay
            record_time_spent_use_case: Use case for recording time
            record_worklog_use_case: Use case for recording worklog
            request_subtask_creation_use_case: Use case for subtask requests
            user_config_repository: Repository for user config
            queue_manager: Task queue manager
        """
        self.record_delay = record_delay_reason_use_case
        self.record_time = record_time_spent_use_case
        self.record_worklog = record_worklog_use_case
        self.request_subtask = request_subtask_creation_use_case
        self.user_config_repository = user_config_repository
        self.queue_manager = queue_manager
        self.task_sender = None  # Will be set by SendDailyTaskRemindersUseCase

    def create_delay_reason_keyboard(self) -> InlineKeyboardMarkup:
        """Create inline keyboard for delay reasons.

        Returns:
            Inline keyboard markup
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_WAITING_APPROVAL,
                    callback_data="delay_waiting_approval",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_TECHNICAL_BLOCKER,
                    callback_data="delay_technical_blocker",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_OTHER_PRIORITIES,
                    callback_data="delay_other_priorities",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_MISSING_REQUIREMENTS,
                    callback_data="delay_missing_requirements",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_DEPENDENCY_NOT_READY,
                    callback_data="delay_dependency_not_ready",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_OTHER,
                    callback_data="delay_other",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.REQUEST_SUBTASKS,
                    callback_data="request_subtasks",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.SKIP_TASK,
                    callback_data="skip_task",
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_hours_keyboard(self, prefix: str = "hours") -> InlineKeyboardMarkup:
        """Create inline keyboard for hours selection.

        Args:
            prefix: Callback data prefix (hours or worklog)

        Returns:
            Inline keyboard markup
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_1,
                    callback_data=f"{prefix}_1",
                ),
                InlineKeyboardButton(
                    persian_messages.HOURS_2,
                    callback_data=f"{prefix}_2",
                ),
            ],
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_3,
                    callback_data=f"{prefix}_3",
                ),
                InlineKeyboardButton(
                    persian_messages.HOURS_4,
                    callback_data=f"{prefix}_4",
                ),
            ],
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_6,
                    callback_data=f"{prefix}_6",
                ),
                InlineKeyboardButton(
                    persian_messages.HOURS_8,
                    callback_data=f"{prefix}_8",
                ),
            ],
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_CUSTOM,
                    callback_data=f"{prefix}_custom",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.SKIP_TASK,
                    callback_data="skip_task",
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def handle_callback(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle callback query from inline keyboard.

        Args:
            update: Telegram update
            context: Callback context
        """
        query = update.callback_query
        await query.answer()
        
        data = query.data
        chat_id = query.message.chat_id
        
        LOGGER.info(f"Callback received: data='{data}', chat_id={chat_id}")
        
        try:
            if data.startswith("delay_"):
                LOGGER.info("Processing delay callback")
                await self._handle_delay_callback(query, context, data)
            elif data.startswith("hours_"):
                LOGGER.info("Processing hours callback")
                await self._handle_hours_callback(query, context, data)
            elif data.startswith("worklog_"):
                LOGGER.info("Processing worklog callback")
                await self._handle_worklog_callback(query, context, data)
            elif data == "request_subtasks":
                LOGGER.info("Processing subtask request")
                await self._handle_subtask_request(query, context)
            elif data == "skip_task":
                LOGGER.info("Processing skip task")
                await query.edit_message_text(persian_messages.TASK_SKIPPED)
                # Send next task
                await self._send_next_task_for_user(chat_id)
            
        except Exception as e:
            LOGGER.error(f"Error handling callback: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ خطا در پردازش: {str(e)}"
            )

    async def _handle_delay_callback(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Handle delay reason callback.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data
        """
        if data == "delay_other":
            context.user_data["state"] = self.WAITING_CUSTOM_DELAY
            await query.edit_message_text(
                persian_messages.ENTER_CUSTOM_DELAY_REASON
            )
            return
        
        delay_mapping = {
            "delay_waiting_approval": DelayReason.WAITING_APPROVAL,
            "delay_technical_blocker": DelayReason.TECHNICAL_BLOCKER,
            "delay_other_priorities": DelayReason.OTHER_PRIORITIES,
            "delay_missing_requirements": DelayReason.MISSING_REQUIREMENTS,
            "delay_dependency_not_ready": DelayReason.DEPENDENCY_NOT_READY,
        }
        
        delay_reason = delay_mapping.get(data)
        
        if delay_reason:
            chat_id = query.message.chat_id
            queue = self.queue_manager.get_queue(chat_id)
            if not queue:
                await query.edit_message_text("❌ خطا: تسک یافت نشد")
                return
                
            task = queue.get_current()
            if not task:
                await query.edit_message_text("❌ خطا: تسک یافت نشد")
                return
            
            user_config = self.user_config_repository.get_user_config(
                query.from_user.username
            )
            
            if user_config:
                await self.record_delay.execute(
                    issue_key=task.issue_key,
                    jira_username=user_config.jira_username,
                    telegram_username=query.from_user.username,
                    delay_reason=delay_reason,
                )
                
                await query.edit_message_text(
                    persian_messages.DELAY_RECORDED
                )
                
                # Send next task
                await self._send_next_task_for_user(chat_id)

    async def _handle_hours_callback(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Handle hours spent callback.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data
        """
        if data == "hours_custom":
            context.user_data["state"] = self.WAITING_CUSTOM_HOURS
            context.user_data["hours_type"] = "progress"
            await query.edit_message_text(
                persian_messages.ENTER_CUSTOM_HOURS
            )
            return
        
        hours_str = data.split("_")[1]
        try:
            hours = float(hours_str)
        except ValueError:
            return
        
        chat_id = query.message.chat_id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            query.from_user.username
        )
        
        if user_config:
            await self.record_time.execute(
                issue_key=task.issue_key,
                jira_username=user_config.jira_username,
                telegram_username=query.from_user.username,
                hours_spent=hours,
            )
            
            await query.edit_message_text(
                persian_messages.HOURS_RECORDED.format(hours)
            )
            
            # Send next task
            await self._send_next_task_for_user(chat_id)

    async def _handle_worklog_callback(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Handle worklog callback.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data
        """
        if data == "worklog_custom":
            context.user_data["state"] = self.WAITING_CUSTOM_HOURS
            context.user_data["hours_type"] = "worklog"
            await query.edit_message_text(
                persian_messages.ENTER_CUSTOM_HOURS
            )
            return
        
        hours_str = data.split("_")[1]
        try:
            hours = float(hours_str)
        except ValueError:
            return
        
        chat_id = query.message.chat_id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            query.from_user.username
        )
        
        if user_config:
            await self.record_worklog.execute(
                issue_key=task.issue_key,
                jira_username=user_config.jira_username,
                telegram_username=query.from_user.username,
                hours=hours,
            )
            
            await query.edit_message_text(
                persian_messages.WORKLOG_RECORDED.format(hours)
            )
            
            # Send next task
            await self._send_next_task_for_user(chat_id)

    async def _handle_subtask_request(
        self,
        query,
        context: CallbackContext,
    ) -> None:
        """Handle subtask creation request.

        Args:
            query: Callback query
            context: Callback context
        """
        chat_id = query.message.chat_id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            query.from_user.username
        )
        
        if user_config:
            await self.request_subtask.execute(
                issue_key=task.issue_key,
                issue_summary=task.summary,
                project_key=task.project_key,
                jira_username=user_config.jira_username,
                telegram_username=query.from_user.username,
            )
            
            await query.edit_message_text(
                persian_messages.SUBTASK_REQUEST_SENT
            )

    async def handle_text_message(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle text message (for custom input).

        Args:
            update: Telegram update
            context: Callback context
        """
        state = context.user_data.get("state")
        
        if state == self.WAITING_CUSTOM_HOURS:
            await self._handle_custom_hours(update, context)
        elif state == self.WAITING_CUSTOM_DELAY:
            await self._handle_custom_delay(update, context)

    async def _handle_custom_hours(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle custom hours input.

        Args:
            update: Telegram update
            context: Callback context
        """
        try:
            hours = float(update.message.text)
            
            if hours <= 0 or hours > 24:
                await update.message.reply_text(
                    persian_messages.ERROR_INVALID_HOURS
                )
                return
            
            chat_id = update.effective_chat.id
            queue = self.queue_manager.get_queue(chat_id)
            if not queue:
                await update.message.reply_text("❌ خطا: تسک یافت نشد")
                return
                
            task = queue.get_current()
            if not task:
                await update.message.reply_text("❌ خطا: تسک یافت نشد")
                return
            
            hours_type = context.user_data.get("hours_type", "progress")
            
            user_config = self.user_config_repository.get_user_config(
                update.effective_user.username
            )
            
            if user_config:
                if hours_type == "worklog":
                    await self.record_worklog.execute(
                        issue_key=task.issue_key,
                        jira_username=user_config.jira_username,
                        telegram_username=update.effective_user.username,
                        hours=hours,
                    )
                    await update.message.reply_text(
                        persian_messages.WORKLOG_RECORDED.format(hours)
                    )
                else:
                    await self.record_time.execute(
                        issue_key=task.issue_key,
                        jira_username=user_config.jira_username,
                        telegram_username=update.effective_user.username,
                        hours_spent=hours,
                    )
                    await update.message.reply_text(
                        persian_messages.HOURS_RECORDED.format(hours)
                    )
                
                context.user_data.pop("state", None)
                context.user_data.pop("hours_type", None)
                
                # Send next task
                await self._send_next_task_for_user(chat_id)
                    
        except ValueError:
            await update.message.reply_text(
                persian_messages.ERROR_INVALID_HOURS
            )

    async def _handle_custom_delay(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle custom delay reason input.

        Args:
            update: Telegram update
            context: Callback context
        """
        delay_text = update.message.text
        
        chat_id = update.effective_chat.id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await update.message.reply_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await update.message.reply_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            update.effective_user.username
        )
        
        if user_config:
            await self.record_delay.execute(
                issue_key=task.issue_key,
                jira_username=user_config.jira_username,
                telegram_username=update.effective_user.username,
                delay_reason=DelayReason.OTHER,
                delay_reason_text=delay_text,
            )
            
            await update.message.reply_text(
                persian_messages.DELAY_RECORDED
            )
            
            context.user_data.pop("state", None)
            
            # Send next task
            await self._send_next_task_for_user(chat_id)

    async def _send_next_task_for_user(self, chat_id: int) -> None:
        """Send next task for user.

        Args:
            chat_id: User's chat ID
        """
        LOGGER.info(f"_send_next_task_for_user called for chat_id {chat_id}")
        
        if self.task_sender:
            LOGGER.info(f"Calling task_sender for chat_id {chat_id}")
            await self.task_sender(chat_id)
        else:
            LOGGER.error("task_sender is not set!")
