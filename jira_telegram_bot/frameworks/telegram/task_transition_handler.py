from __future__ import annotations

from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler

from jira_telegram_bot.use_cases.interfaces.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.telegram_commands.transition_task import JiraTaskTransition


class TaskTransitionHandler(TaskHandlerInterface):
    def __init__(self, task_transition_use_case: JiraTaskTransition):
        self.task_transition_use_case = task_transition_use_case

    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler(
                    "transition",
                    self.task_transition_use_case.start_transition,
                ),
            ],
            states={
                self.task_transition_use_case.ASSIGNEE: [
                    CallbackQueryHandler(self.task_transition_use_case.select_assignee),
                ],
                self.task_transition_use_case.TASK_SELECTION: [
                    CallbackQueryHandler(
                        self.task_transition_use_case.show_task_details,
                    ),
                ],
                self.task_transition_use_case.TASK_ACTION: [
                    CallbackQueryHandler(
                        self.task_transition_use_case.handle_task_action,
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Task transition cancelled.")
        return ConversationHandler.END
