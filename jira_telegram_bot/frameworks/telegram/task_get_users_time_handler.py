from __future__ import annotations

from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.task_get_users_time import TaskGetUsersTime


class TaskGetUsersTimeHandler(TaskHandlerInterface):
    """
    Conversation handler for the 'get_users_time' command.
    """

    def __init__(self, task_get_users_time_use_case: TaskGetUsersTime):
        self.task_get_users_time_use_case = task_get_users_time_use_case

    def get_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[
                CommandHandler(
                    "get_users_time",
                    self.task_get_users_time_use_case.start_get_users_time,
                ),
            ],
            states={
                TaskGetUsersTime.ENTER_FIRST_DAY: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_get_users_time_use_case.get_first_day,
                    ),
                ],
                TaskGetUsersTime.ENTER_DAYS: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_get_users_time_use_case.get_days,
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Report generation cancelled.")
        return ConversationHandler.END
