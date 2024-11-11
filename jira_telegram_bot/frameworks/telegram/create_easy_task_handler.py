from __future__ import annotations

from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.use_cases.create_easy_task import JiraEasyTaskCreation
from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)


class EasyTaskHandler(TaskHandlerInterface):
    def __init__(self, easy_task_use_case: JiraEasyTaskCreation):
        self.easy_task_use_case = easy_task_use_case

    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("create_easy_task", self.easy_task_use_case.start),
            ],
            states={
                self.easy_task_use_case.PROJECT: [
                    CallbackQueryHandler(self.easy_task_use_case.add_project),
                ],
                self.easy_task_use_case.SUMMARY: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.easy_task_use_case.add_summary,
                    ),
                ],
                self.easy_task_use_case.DESCRIPTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.easy_task_use_case.add_description,
                    ),
                ],
                self.easy_task_use_case.COMPONENT: [
                    CallbackQueryHandler(self.easy_task_use_case.add_component),
                ],
                self.easy_task_use_case.TASK_TYPE: [
                    CallbackQueryHandler(self.easy_task_use_case.add_task_type),
                ],
                self.easy_task_use_case.STORY_POINTS: [
                    CallbackQueryHandler(self.easy_task_use_case.add_story_points),
                ],
                self.easy_task_use_case.SPRINT: [
                    CallbackQueryHandler(self.easy_task_use_case.add_sprint),
                ],
                self.easy_task_use_case.ATTACHMENT: [
                    MessageHandler(
                        filters.PHOTO | filters.Document.ALL,
                        self.easy_task_use_case.add_attachment,
                    ),
                ],
                self.easy_task_use_case.EPIC_LINK: [
                    CallbackQueryHandler(self.easy_task_use_case.add_epic_link),
                ],
                self.easy_task_use_case.RELEASE: [
                    CallbackQueryHandler(self.easy_task_use_case.add_release),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Easy task creation process cancelled.")
        return ConversationHandler.END
