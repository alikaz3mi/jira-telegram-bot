from __future__ import annotations

from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.user_settings import UserSettingsConversation


class UserSettingsHandler(TaskHandlerInterface):
    def __init__(self, settings_use_case: UserSettingsConversation):
        self.settings_use_case = settings_use_case

    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("setting", self.settings_use_case.start),
            ],
            states={
                self.settings_use_case.MAIN_MENU: [
                    CallbackQueryHandler(self.settings_use_case.handle_main_menu),
                ],
                self.settings_use_case.CHOOSE_USER: [
                    CallbackQueryHandler(self.settings_use_case.choose_user_to_edit),
                ],
                self.settings_use_case.EDIT_SETTINGS: [
                    CallbackQueryHandler(
                        self.settings_use_case.toggle_field,
                        pattern=r"^toggle\|",
                    ),
                    CallbackQueryHandler(
                        self.settings_use_case.done_editing,
                        pattern="^done$",
                    ),
                ],
                self.settings_use_case.WAIT_NEW_USER_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.settings_use_case.wait_new_user_username,
                    ),
                ],
                self.settings_use_case.WAIT_NEW_USER_JIRA_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.settings_use_case.wait_new_user_jira_username,
                    ),
                ],
                self.settings_use_case.WAIT_NEW_USER_CHAT_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.settings_use_case.wait_new_user_chat_id,
                    ),
                ],
                self.settings_use_case.EDIT_NEW_USER_TOGGLES: [
                    CallbackQueryHandler(
                        self.settings_use_case.toggle_field,
                        pattern=r"^toggle\|",
                    ),
                    CallbackQueryHandler(
                        self.settings_use_case.done_editing_new_user,
                        pattern="^done$",
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.settings_use_case.cancel)],
        )

    async def cancel(self, update, context):
        await update.message.reply_text("Task creation process cancelled.")
        return ConversationHandler.END
