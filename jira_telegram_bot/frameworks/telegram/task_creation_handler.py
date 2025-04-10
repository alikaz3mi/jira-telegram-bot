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
                CommandHandler("create_task", self.task_creation_use_case.start),
            ],
            states={
                self.task_creation_use_case.PROJECT: [
                    CallbackQueryHandler(self.task_creation_use_case.select_project),
                ],
                self.task_creation_use_case.SUMMARY: [
                    MessageHandler(
                        (filters.TEXT & ~filters.COMMAND) | filters.FORWARDED,
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
                    CallbackQueryHandler(
                        self.task_creation_use_case.toggle_component_selection,
                    ),
                ],
                self.task_creation_use_case.ASSIGNEE: [
                    CallbackQueryHandler(self.task_creation_use_case.add_assignee),
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
                    CallbackQueryHandler(self.task_creation_use_case.add_priority),
                ],
                self.task_creation_use_case.SPRINT: [
                    CallbackQueryHandler(self.task_creation_use_case.add_sprint),
                ],
                self.task_creation_use_case.EPIC: [
                    CallbackQueryHandler(self.task_creation_use_case.add_epic),
                ],
                self.task_creation_use_case.RELEASE: [
                    CallbackQueryHandler(self.task_creation_use_case.add_release),
                ],
                self.task_creation_use_case.TASK_TYPE: [
                    CallbackQueryHandler(self.task_creation_use_case.add_task_type),
                ],
                # NEW STEP for picking parent story if sub-task
                self.task_creation_use_case.SELECT_STORY: [
                    CallbackQueryHandler(self.task_creation_use_case.add_subtask_story),
                ],
                self.task_creation_use_case.STORY_POINTS: [
                    CallbackQueryHandler(self.task_creation_use_case.add_story_points),
                ],
                self.task_creation_use_case.DEADLINE: [
                    CallbackQueryHandler(self.task_creation_use_case.add_deadline),
                ],
                self.task_creation_use_case.LABELS: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.toggle_label_selection,
                    ),
                ],
                self.task_creation_use_case.LABELS_NEW: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.task_creation_use_case.add_new_label,
                    ),
                ],
                self.task_creation_use_case.ATTACHMENT: [
                    MessageHandler(
                        filters.PHOTO
                        | filters.Document.ALL
                        | filters.AUDIO
                        | filters.VIDEO
                        | (filters.TEXT & ~filters.COMMAND),
                        self.task_creation_use_case.add_attachment,
                    ),
                ],
                self.task_creation_use_case.CREATE_ANOTHER: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.handle_create_another,
                    ),
                ],
                # NEW STEP for keep-fields multi-select
                self.task_creation_use_case.KEEP_FIELDS: [
                    CallbackQueryHandler(
                        self.task_creation_use_case.toggle_keep_field_selection,
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Task creation process cancelled.")
        return ConversationHandler.END
