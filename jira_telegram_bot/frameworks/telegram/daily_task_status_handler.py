"""Telegram handler for daily task status."""
from __future__ import annotations

from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from jira_telegram_bot.use_cases.interfaces.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import (
    DailyTaskStatus,
)


class DailyTaskStatusHandler(TaskHandlerInterface):
    """Handler for daily task status conversation."""

    def __init__(self, daily_task_status_use_case: DailyTaskStatus):
        """Initialize the handler.
        
        Args:
            daily_task_status_use_case: The daily task status use case.
        """
        self.use_case = daily_task_status_use_case

    def get_handler(self) -> ConversationHandler:
        """Get the conversation handler.
        
        Returns:
            ConversationHandler for daily task status.
        """
        return ConversationHandler(
            entry_points=[
                CommandHandler("daily_status", self.use_case.start_daily_status),
            ],
            states={
                self.use_case.TASK_DISPLAY: [
                    CallbackQueryHandler(
                        self.use_case.handle_task_action,
                        pattern=r"^action\|",
                    ),
                ],
                self.use_case.TIME_SPENT: [
                    CallbackQueryHandler(
                        self.use_case.handle_time_spent,
                        pattern=r"^(hours\||back)$",
                    ),
                ],
                self.use_case.DELAY_REASON: [
                    CallbackQueryHandler(
                        self.use_case.handle_delay_reason,
                        pattern=r"^(delay\||back)$",
                    ),
                ],
                self.use_case.DELAY_COMMENT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.use_case.handle_delay_comment,
                    ),
                    CommandHandler("skip", self.use_case.handle_delay_comment),
                ],
                self.use_case.STATUS_TRANSITION: [
                    CallbackQueryHandler(
                        self.use_case.handle_transition,
                        pattern=r"^(transition\||back)$",
                    ),
                ],
                self.use_case.SUBTASK_REQUEST: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.use_case.handle_subtask_request,
                    ),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.use_case.cancel),
            ],
            per_user=True,
            per_chat=True,
        )

    async def cancel(self, update, context):
        """Cancel handler fallback.
        
        Args:
            update: Telegram update.
            context: Callback context.
            
        Returns:
            ConversationHandler.END
        """
        return await self.use_case.cancel(update, context)
