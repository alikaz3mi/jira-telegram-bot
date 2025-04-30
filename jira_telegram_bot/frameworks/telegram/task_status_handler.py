from __future__ import annotations

from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.telegram_commands.task_status import TaskStatus


class TaskStatusHandler(TaskHandlerInterface):
    def __init__(self, task_status_use_case: TaskStatus):
        self.task_status_use_case = task_status_use_case

    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("status", self.task_status_use_case.get_task_status),
            ],
            states={
                self.task_status_use_case.TASK_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_status_use_case.fetch_task_details,
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Status check cancelled.")
        return ConversationHandler.END
