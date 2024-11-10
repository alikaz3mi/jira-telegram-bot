from __future__ import annotations

from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.use_cases.create_task import JiraTaskCreation
from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)


class TaskCreationHandler(TaskHandlerInterface):
    def __init__(self, task_creation_use_case: JiraTaskCreation):
        self.task_creation_use_case = task_creation_use_case

    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("start", self.task_creation_use_case.select_project),
            ],
            states={
                self.task_creation_use_case.PROJECT: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.select_project_callback,
                    ),
                ],
                self.task_creation_use_case.SUMMARY: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_creation_use_case.add_summary,
                    ),
                ],
                self.task_creation_use_case.DESCRIPTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_creation_use_case.add_description,
                    ),
                ],
                self.task_creation_use_case.COMPONENT: [
                    CallbackQueryHandler(self.task_creation_use_case.button_component),
                ],
                self.task_creation_use_case.ASSIGNEE: [
                    CallbackQueryHandler(self.task_creation_use_case.button_assignee),
                ],
                self.task_creation_use_case.ASSIGNEE_SEARCH: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_creation_use_case.search_assignee,
                    ),
                ],
                self.task_creation_use_case.ASSIGNEE_RESULT: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.select_assignee_from_search,
                    ),
                ],
                self.task_creation_use_case.PRIORITY: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.button_priority_callback,
                    ),
                ],
                self.task_creation_use_case.SPRINT: [
                    CallbackQueryHandler(self.task_creation_use_case.button_sprint),
                ],
                self.task_creation_use_case.EPIC: [
                    CallbackQueryHandler(self.task_creation_use_case.button_epic),
                ],
                self.task_creation_use_case.TASK_TYPE: [
                    CallbackQueryHandler(self.task_creation_use_case.button_task_type),
                ],
                self.task_creation_use_case.STORY_SELECTION: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.button_story_selection,
                    ),
                ],
                self.task_creation_use_case.STORY_POINTS: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.button_story_points,
                    ),
                ],
                self.task_creation_use_case.IMAGE: [
                    MessageHandler(
                        filters.PHOTO | (filters.TEXT & ~filters.COMMAND),
                        self.task_creation_use_case.handle_image,
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        """Handles the cancel command to exit the task creation process."""
        await update.message.reply_text("Task creation process cancelled.")
        return ConversationHandler.END
