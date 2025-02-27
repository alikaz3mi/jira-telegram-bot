from __future__ import annotations

from typing import List

from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.authentication import check_user_allowed
from jira_telegram_bot.use_cases.interface.user_config_interface import (
    UserConfigInterface,
)


class UserSettingsConversation:
    (
        MAIN_MENU,
        CHOOSE_USER,
        EDIT_SETTINGS,
        WAIT_NEW_USER_USERNAME,
        WAIT_NEW_USER_JIRA_USERNAME,
        WAIT_NEW_USER_CHAT_ID,
        EDIT_NEW_USER_TOGGLES,
    ) = range(7)

    def __init__(
        self,
        user_config_repo: UserConfigInterface,
        admin_usernames: List[str],
    ):
        """
        :param user_config_repo: your user config repository to load/save user configs
        :param admin_usernames: list of telegram usernames with admin privileges
        """
        self.user_config_repo = user_config_repo
        self.admin_usernames = set(admin_usernames)

    def build_main_menu(self, is_admin: bool) -> InlineKeyboardMarkup:
        """
        If user is admin => show 3 buttons
        If not => show only 'modify my settings'
        """
        keyboard = []
        row = [
            InlineKeyboardButton("Modify My Settings", callback_data="self_settings"),
        ]
        keyboard.append(row)
        if is_admin:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "Modify Another User's Settings",
                        callback_data="other_settings",
                    ),
                ],
            )
            keyboard.append(
                [
                    InlineKeyboardButton("Define New User", callback_data="new_user"),
                ],
            )
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: CallbackContext) -> int:
        """
        /setting entry point
        """
        if not await check_user_allowed(update):
            await update.message.reply_text("You are not allowed to use settings.")
            return ConversationHandler.END

        context.user_data.clear()

        is_admin = update.message.from_user.username in self.admin_usernames

        kb = self.build_main_menu(is_admin)
        await update.message.reply_text("Welcome to Settings!", reply_markup=kb)
        return self.MAIN_MENU

    async def handle_main_menu(self, update: Update, context: CallbackContext) -> int:
        """User clicked on a main-menu button."""
        query = update.callback_query
        await query.answer()
        data = query.data
        user_username = query.from_user.username
        is_admin = user_username in self.admin_usernames

        if data == "self_settings":
            user_cfg = self.user_config_repo.get_user_config(user_username)
            if not user_cfg:
                user_cfg = self.user_config_repo.create_user_config(
                    telegram_username=user_username,
                    telegram_user_chat_id=query.from_user.id,
                    jira_username=user_username,
                )
            context.user_data["current_edit_username"] = user_username
            await query.edit_message_text(
                text=f"Editing your settings ({user_username}):",
                reply_markup=self.build_toggles_kb(user_cfg),
            )
            return self.EDIT_SETTINGS

        if (data == "other_settings" or data == "new_user") and not is_admin:
            await query.edit_message_text("You are not an admin!")
            return ConversationHandler.END

        if data == "other_settings":
            all_users = self.user_config_repo.list_all_users()
            if not all_users:
                await query.edit_message_text("No user configs exist yet.")
                return ConversationHandler.END

            buttons = []
            for uname in all_users:
                buttons.append(
                    [InlineKeyboardButton(uname, callback_data=f"user|{uname}")],
                )

            await query.edit_message_text(
                text="Choose which user to edit:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return self.CHOOSE_USER

        if data == "new_user":
            await query.edit_message_text(
                "Please enter the new user's Telegram username (without @):",
            )
            return self.WAIT_NEW_USER_USERNAME

        return ConversationHandler.END

    async def choose_user_to_edit(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        After user clicked a username in the "other_settings" path.
        """
        query = update.callback_query
        await query.answer()
        data = query.data
        if not data.startswith("user|"):
            await query.edit_message_text("Invalid user selection.")
            return ConversationHandler.END

        chosen_user = data.split("|")[1]
        context.user_data["current_edit_username"] = chosen_user
        user_cfg = self.user_config_repo.get_user_config(chosen_user)
        if not user_cfg:
            await query.edit_message_text("No config found for that user.")
            return ConversationHandler.END

        await query.edit_message_text(
            text=f"Editing settings for {chosen_user}:",
            reply_markup=self.build_toggles_kb(user_cfg),
        )
        return self.EDIT_SETTINGS

    def build_toggles_kb(self, user_cfg) -> InlineKeyboardMarkup:
        """
        Build an inline keyboard that shows each field as a toggle:
          [component ✔], [task_type], etc.
        "✔" if set_field = True, else blank.
        Then a 'Done' button at the bottom.

        # <-- NEW: We now add "deadline" and "labels" in the toggles as well.
        """
        field_names = [
            "project",
            "component",
            "task_type",
            "story_point",
            "attachment",
            "epic_link",
            "release",
            "sprint",
            "assignee",
            "priority",
            "deadline",  # <-- NEW
            "labels",  # <-- NEW
        ]

        rows = []
        temp_row = []

        for fname in field_names:
            field_config = getattr(user_cfg, fname, None)
            if not field_config:
                # If the user_config does not have that field for some reason,
                # skip it. (But normally it should exist.)
                continue
            check_mark = "✔" if field_config.set_field else ""
            button_text = f"{fname} {check_mark}"
            cb_data = f"toggle|{fname}"
            temp_row.append(InlineKeyboardButton(button_text, callback_data=cb_data))

            if len(temp_row) == 2:
                rows.append(temp_row)
                temp_row = []

        if temp_row:
            rows.append(temp_row)

        rows.append([InlineKeyboardButton("Done", callback_data="done")])
        return InlineKeyboardMarkup(rows)

    async def toggle_field(self, update: Update, context: CallbackContext) -> int:
        """
        The user clicked on a toggle button for a field, e.g. "toggle|component".
        This flips the `set_field` boolean in user_cfg for that field.
        """
        query = update.callback_query
        await query.answer()
        data = query.data
        username = context.user_data.get("current_edit_username", None)
        if not username:
            await query.edit_message_text("No user to edit?!")
            return ConversationHandler.END

        user_cfg = self.user_config_repo.get_user_config(username)
        if not user_cfg:
            await query.edit_message_text("No config found for that user.")
            return ConversationHandler.END

        # Extract the field name
        _, field_name = data.split("|", 1)
        field_obj = getattr(user_cfg, field_name, None)
        if not field_obj:
            await query.edit_message_text("Invalid field.")
            return ConversationHandler.END

        # Flip the set_field
        field_obj.set_field = not field_obj.set_field

        # Save the updated config
        self.user_config_repo.save_user_config(username, user_cfg)

        # Rebuild the toggles to reflect new checkmark
        kb = self.build_toggles_kb(user_cfg)

        # Edit the message to say "Settings updated!" but keep same toggles
        await query.edit_message_text(
            text="Settings updated!",
            reply_markup=kb,
        )
        return self.EDIT_SETTINGS

    async def done_editing(self, update: Update, context: CallbackContext) -> int:
        """
        User clicked "Done" in the toggles menu.
        """
        query = update.callback_query
        await query.answer()

        username = context.user_data.get("current_edit_username", None)
        if username:
            await query.edit_message_text(f"Finished editing settings for {username}.")
        else:
            await query.edit_message_text("Finished editing settings.")
        return ConversationHandler.END

    async def wait_new_user_username(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        The user is asked to type the new user's Telegram username.
        """
        new_username = update.message.text.strip().lstrip("@")
        context.user_data["new_user_username"] = new_username
        await update.message.reply_text(
            "Great. Now enter the new user's Jira username:",
        )
        return self.WAIT_NEW_USER_JIRA_USERNAME

    async def wait_new_user_jira_username(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        Next step: ask for chat id
        """
        jira_username = update.message.text.strip()
        context.user_data["new_user_jira_username"] = jira_username
        await update.message.reply_text(
            "Now please enter the new user's Telegram chat ID (integer):",
        )
        return self.WAIT_NEW_USER_CHAT_ID

    async def wait_new_user_chat_id(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        Finally, we define a blank user config and allow toggles.
        """
        chat_id_text = update.message.text.strip()
        try:
            chat_id = int(chat_id_text)
        except ValueError:
            await update.message.reply_text("Invalid chat ID. Please try again:")
            return self.WAIT_NEW_USER_CHAT_ID

        new_uname = context.user_data["new_user_username"]
        new_jira = context.user_data["new_user_jira_username"]

        # Create the user config in the repo
        user_cfg = self.user_config_repo.create_user_config(
            telegram_username=new_uname,
            telegram_user_chat_id=chat_id,
            jira_username=new_jira,
        )
        # store in context
        context.user_data["current_edit_username"] = new_uname

        # Now show toggles for the new user
        await update.message.reply_text(
            text=f"User {new_uname} created. Now set which fields are on/off:",
            reply_markup=self.build_toggles_kb(user_cfg),
        )
        return self.EDIT_NEW_USER_TOGGLES

    async def done_editing_new_user(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        After pressing Done in the new user toggles
        """
        query = update.callback_query
        await query.answer()
        new_uname = context.user_data.get("current_edit_username", "")
        await query.edit_message_text(f"All done! New user {new_uname} created.")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: CallbackContext) -> int:
        """User typed /cancel or something similar."""
        await update.message.reply_text("Settings process cancelled.")
        return ConversationHandler.END
