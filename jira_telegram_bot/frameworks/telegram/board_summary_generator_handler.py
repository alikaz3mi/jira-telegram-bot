from __future__ import annotations

from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.use_cases.telegram_commands.board_summary_generator import BoardSummaryGenerator
from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)


class BoardSummaryGeneratorHandler(TaskHandlerInterface):
    def __init__(self, board_summary_generator: BoardSummaryGenerator):
        self.board_summary_generator = board_summary_generator

    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("summary_tasks", self.board_summary_generator.start),
            ],
            states={
                self.board_summary_generator.PROJECT: [
                    CallbackQueryHandler(self.board_summary_generator.select_project),
                ],
                self.board_summary_generator.COMPONENT: [
                    CallbackQueryHandler(self.board_summary_generator.add_component),
                ],
                self.board_summary_generator.ASSIGNEE: [
                    CallbackQueryHandler(self.board_summary_generator.add_assignee),
                ],
                self.board_summary_generator.ASSIGNEE_SEARCH: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.board_summary_generator.search_assignee,
                    ),
                ],
                self.board_summary_generator.ASSIGNEE_RESULT: [
                    CallbackQueryHandler(
                        self.board_summary_generator.select_assignee_from_search,
                    ),
                ],
                self.board_summary_generator.SPRINT: [
                    CallbackQueryHandler(self.board_summary_generator.add_sprint),
                ],
                self.board_summary_generator.EPIC: [
                    CallbackQueryHandler(self.board_summary_generator.add_epic),
                ],
                self.board_summary_generator.RELEASE: [
                    CallbackQueryHandler(self.board_summary_generator.add_release),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Task fetching process cancelled.")
        return ConversationHandler.END
