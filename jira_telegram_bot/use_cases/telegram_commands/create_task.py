from __future__ import annotations

import datetime
from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import aiohttp
from telegram import CallbackQuery
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class JiraTaskCreation:
    (
        PROJECT,
        SUMMARY,
        DESCRIPTION,
        COMPONENT,
        ASSIGNEE,
        PRIORITY,
        SPRINT,
        EPIC,
        RELEASE,
        TASK_TYPE,
        STORY_POINTS,
        DEADLINE,
        LABELS,
        LABELS_NEW,
        ATTACHMENT,
        ASSIGNEE_SEARCH,
        ASSIGNEE_RESULT,
        CREATE_ANOTHER,
        KEEP_FIELDS,  # <-- For multi-select of fields to keep
        SELECT_STORY,  # <-- For sub-task parent story selection
    ) = range(20)

    DEADLINE_OPTIONS = [
        ("0", "Current Day"),
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
        ("6", "6"),
        ("7", "7"),
        ("8", "8"),
        ("9", "9"),
        ("10", "10"),
        ("11", "11"),
        ("12", "12"),
        ("13", "13"),
        ("14", "14"),
        ("21", "21"),
        ("30", "30"),
    ]

    def __init__(
        self,
        jira_repository: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        self.jira_repository = jira_repository
        self.user_config = user_config
        self.media_group_timeout = 1.0
        self.STORY_POINTS_VALUES = [
            0.25,
            0.5,
            0.75,
            1,
            1.5,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            10,
            12,
            14,
            21,
        ]

    def build_keyboard(
        self,
        options: List[str],
        data: Optional[List[str]] = None,
        include_skip: bool = False,
        row_width: int = 2,
        extra_buttons: Optional[List[List[InlineKeyboardButton]]] = None,
    ) -> InlineKeyboardMarkup:
        """
        Generic helper to build a grid keyboard. `options` are the button texts,
        `data` are the callback_data (if they differ from texts).
        """
        if not data:
            data = options
        keyboard = []
        for i in range(0, len(options), row_width):
            row = []
            for j, option in enumerate(options[i : i + row_width]):
                row.append(InlineKeyboardButton(text=option, callback_data=data[i + j]))
            keyboard.append(row)

        if extra_buttons:
            keyboard.extend(extra_buttons)
        if include_skip:
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        return InlineKeyboardMarkup(keyboard)

    def build_component_selection_keyboard(
        self,
        all_components: List[str],
        selected: List[str],
    ) -> InlineKeyboardMarkup:
        """
        Build a toggle-style keyboard for multi-component selection.
        Shows a "✔" next to currently selected components.
        Includes "Done" and "Skip" at the bottom.
        """
        keyboard = []
        row_width = 2
        for i in range(0, len(all_components), row_width):
            row = []
            for comp in all_components[i : i + row_width]:
                mark = "✔" if comp in selected else ""
                btn_text = f"{comp} {mark}"
                row.append(
                    InlineKeyboardButton(btn_text, callback_data=f"cmp|{comp}"),
                )
            keyboard.append(row)
        bottom_row = [
            InlineKeyboardButton("Done", callback_data="cmp_done"),
            InlineKeyboardButton("Skip", callback_data="skip"),
        ]
        keyboard.append(bottom_row)
        return InlineKeyboardMarkup(keyboard)

    def build_label_selection_keyboard(
        self,
        all_labels: List[str],
        selected: List[str],
    ) -> InlineKeyboardMarkup:
        """
        Build a toggle-style keyboard for multi-label selection.
        Shows a "✔" next to currently selected labels.
        Includes "New Label", "Done", and "Skip" at the bottom.
        """
        keyboard = []
        row_width = 2
        for i in range(0, len(all_labels), row_width):
            row = []
            for lbl in all_labels[i : i + row_width]:
                mark = "✔" if lbl in selected else ""
                btn_text = f"{lbl} {mark}"
                row.append(
                    InlineKeyboardButton(btn_text, callback_data=f"lbl|{lbl}"),
                )
            keyboard.append(row)

        bottom_row = [
            InlineKeyboardButton("New Label", callback_data="lbl_new"),
            InlineKeyboardButton("Done", callback_data="lbl_done"),
            InlineKeyboardButton("Skip", callback_data="skip"),
        ]
        keyboard.append(bottom_row)
        return InlineKeyboardMarkup(keyboard)

    # -------------------------------------------------------------------------
    #  START
    # -------------------------------------------------------------------------
    async def start(self, update: Update, context: CallbackContext) -> int:
        """User starts conversation with /create_task."""
        if not self.user_config.get_user_config(update.message.from_user.username):
            return ConversationHandler.END

        context.user_data.clear()

        task_data = TaskData()
        task_data.attachments = {
            "images": [],
            "documents": [],
            "videos": [],
            "audio": [],
        }
        task_data.components = []
        task_data.labels = []

        context.user_data["task_data"] = task_data
        config = self.user_config.get_user_config(update.message.from_user.username)
        context.user_data["user_config"] = config

        projects = self.jira_repository.get_projects()
        options = [p.name for p in projects]
        data = [p.key for p in projects]
        reply_markup = self.build_keyboard(options, data, row_width=3)

        await update.message.reply_text(
            "Please select a project from the list below:",
            reply_markup=reply_markup,
        )
        return self.PROJECT

    async def select_project(self, update: Update, context: CallbackContext) -> int:
        """User clicked on a project button."""
        query = update.callback_query
        await query.answer()

        project_key = query.data
        task_data: TaskData = context.user_data["task_data"]
        task_data.project_key = project_key

        LOGGER.info("Project selected: %s", project_key)

        task_data.epics = self.jira_repository.get_epics(project_key)
        task_data.board_id = self.jira_repository.get_board_id(project_key)
        task_data.sprints = (
            self.jira_repository.get_sprints(task_data.board_id)
            if task_data.board_id
            else []
        )
        task_data.task_types = self.jira_repository.get_issue_types_for_project(
            project_key,
        )

        await query.edit_message_text(text="Please enter the task summary:")
        return self.SUMMARY

    # -------------------------------------------------------------------------
    #  SUMMARY / DESCRIPTION
    # -------------------------------------------------------------------------
    async def add_summary(self, update: Update, context: CallbackContext) -> int:
        """User typed or forwarded a summary."""
        task_data: TaskData = context.user_data["task_data"]
        message = update.message

        if message.forward and message.forward_origin:
            text = message.text or message.caption or ""
            lines = text.strip().split("\n")
            task_data.summary = lines[0] if lines else ""
            task_data.description = text
            LOGGER.info("Summary from forwarded message: %s", task_data.summary)

            attachments = task_data.attachments
            if any([message.photo, message.video, message.document, message.audio]):
                await self.process_single_media(message, attachments)

            await update.message.reply_text("Got it! Proceeding to the next step.")
            return self.DESCRIPTION
        else:
            task_data.summary = message.text.strip()
            LOGGER.info("Summary received: %s", task_data.summary)
            msg = await update.message.reply_text(
                'Got it! Now send me the description of the task (or type "skip" to skip).',
            )
            context.user_data["last_inline_message_id"] = msg.message_id
            return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        """User typed a description or 'skip'."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]
        if not task_data.description:
            desc = update.message.text.strip()
            if desc.lower() != "skip":
                task_data.description = desc

        last_message_id = context.user_data["last_inline_message_id"]

        # 1) Skip if user already has components (carried over)
        if task_data.components:
            LOGGER.info("Components already exist, skipping component step.")
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="Components retained from previous task. Proceeding...",
            )
            return await self.ask_assignee_from_text(update, context)

        # 2) If user_cfg says skip or no components
        if not user_cfg.component.set_field:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="Skipping components. Proceeding to the next step...",
            )
            return await self.ask_assignee_from_text(update, context)

        if user_cfg.component.values:
            options = user_cfg.component.values
        else:
            jira_components = self.jira_repository.get_project_components(
                task_data.project_key,
            )
            if not jira_components:
                LOGGER.info("No components found for %s", task_data.project_key)
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=last_message_id,
                    text="No components found. Proceeding to the next step...",
                )
                return await self.ask_assignee_from_text(update, context)
            options = [c.name for c in jira_components]

        context.user_data["available_components"] = options
        task_data.components = []

        reply_markup = self.build_component_selection_keyboard(
            all_components=options,
            selected=task_data.components,
        )
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=last_message_id,
            text=(
                "Got it! Choose one or more components below (toggle on/off). "
                "Press Done when finished, or Skip to skip this step."
            ),
            reply_markup=reply_markup,
        )
        return self.COMPONENT

    # -------------------------------------------------------------------------
    #  COMPONENT
    # -------------------------------------------------------------------------
    async def toggle_component_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        available_components = context.user_data.get("available_components", [])

        data = query.data
        if data.startswith("cmp|"):
            component_name = data.split("|", 1)[1]
            if component_name in task_data.components:
                task_data.components.remove(component_name)
            else:
                task_data.components.append(component_name)

            reply_markup = self.build_component_selection_keyboard(
                all_components=available_components,
                selected=task_data.components,
            )
            await query.edit_message_text(
                text="Toggle components. Press Done when finished, or Skip.",
                reply_markup=reply_markup,
            )
            return self.COMPONENT

        elif data == "cmp_done":
            LOGGER.info("Components selected: %s", task_data.components)
            return await self.ask_assignee(query, context)

        elif data == "skip":
            task_data.components = []
            LOGGER.info("Component selection skipped.")
            return await self.ask_assignee(query, context)

        return self.COMPONENT

    # -------------------------------------------------------------------------
    #  ASSIGNEE
    # -------------------------------------------------------------------------
    async def ask_assignee_from_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        last_message_id = context.user_data["last_inline_message_id"]
        return await self._ask_assignee_common(
            context,
            update.effective_chat.id,
            last_message_id,
        )

    async def ask_assignee(self, query: CallbackQuery, context: CallbackContext) -> int:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_assignee_common(context, chat_id, message_id)

    async def _ask_assignee_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # If we already have an assignee, skip
        if task_data.assignee:
            LOGGER.info("Assignee already set, skipping assignee step.")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Assignee retained from previous task. Proceeding...",
            )
            return await self.ask_priority_from_text_internal(
                context,
                chat_id,
                message_id,
            )

        if not user_cfg.assignee.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping assignee. Proceeding to next step...",
            )
            return await self.ask_priority_from_text_internal(
                context,
                chat_id,
                message_id,
            )

        if user_cfg.assignee.values:
            assignees = user_cfg.assignee.values
        else:
            assignees = self.jira_repository.get_assignees(task_data.project_key)

        if not assignees:
            LOGGER.info("No assignees found.")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="No assignees found. Proceeding to next step...",
            )
            return await self.ask_priority_from_text_internal(
                context,
                chat_id,
                message_id,
            )

        extra_buttons = [[InlineKeyboardButton("Others", callback_data="others")]]
        reply_markup = self.build_keyboard(
            options=assignees,
            data=assignees,
            row_width=2,
            include_skip=True,
            extra_buttons=extra_buttons,
        )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose an assignee from the list below:",
            reply_markup=reply_markup,
        )
        return self.ASSIGNEE

    async def add_assignee(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data == "others":
            await query.edit_message_text("Please enter the username to search for:")
            return self.ASSIGNEE_SEARCH
        elif query.data == "skip":
            task_data.assignee = None
            LOGGER.info("Assignee skipped.")
            return await self.ask_priority_from_query(query, context)
        else:
            task_data.assignee = query.data
            LOGGER.info("Assignee selected: %s", task_data.assignee)
            return await self.ask_priority_from_query(query, context)

    async def search_assignee(self, update: Update, context: CallbackContext) -> int:
        username_query = update.message.text.strip()
        matching_users = self.jira_repository.search_users(username_query)

        last_message_id = context.user_data["last_inline_message_id"]

        if matching_users:
            options = matching_users
            extra_buttons = [[InlineKeyboardButton("Others", callback_data="others")]]
            reply_markup = self.build_keyboard(
                options=options,
                data=options,
                row_width=2,
                include_skip=True,
                extra_buttons=extra_buttons,
            )
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="Select an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE_RESULT
        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="No users found. Please enter a different username:",
            )
            return self.ASSIGNEE_SEARCH

    async def select_assignee_from_search(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data == "others":
            await query.edit_message_text("Please enter the username to search for:")
            return self.ASSIGNEE_SEARCH
        elif query.data == "skip":
            task_data.assignee = None
            LOGGER.info("Assignee skipped.")
            return await self.ask_priority_from_query(query, context)
        else:
            task_data.assignee = query.data
            LOGGER.info("Assignee selected from search: %s", task_data.assignee)
            return await self.ask_priority_from_query(query, context)

    # -------------------------------------------------------------------------
    #  PRIORITY
    # -------------------------------------------------------------------------
    async def ask_priority_from_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        last_message_id = context.user_data["last_inline_message_id"]
        return await self._ask_priority_common(
            context,
            update.effective_chat.id,
            last_message_id,
        )

    async def ask_priority_from_text_internal(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        return await self._ask_priority_common(context, chat_id, message_id)

    async def ask_priority_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_priority_common(context, chat_id, message_id)

    async def _ask_priority_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # Skip if priority is already set
        if task_data.priority:
            LOGGER.info("Priority already set, skipping step.")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Priority retained from previous task. Proceeding...",
            )
            return await self._ask_sprint_common(context, chat_id, message_id)

        if not user_cfg.priority.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping priority. Proceeding to next step...",
            )
            return await self._ask_sprint_common(context, chat_id, message_id)

        if user_cfg.priority.values:
            options = user_cfg.priority.values
        else:
            priorities = self.jira_repository.get_priorities()
            options = [p.name for p in priorities]

        reply_markup = self.build_keyboard(options, include_skip=True, row_width=4)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose a priority from the list below:",
            reply_markup=reply_markup,
        )
        return self.PRIORITY

    async def add_priority(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.priority = query.data
        LOGGER.info("Priority selected: %s", task_data.priority)

        return await self.ask_sprint(query, context)

    # -------------------------------------------------------------------------
    #  SPRINT
    # -------------------------------------------------------------------------
    async def ask_sprint(self, query: CallbackQuery, context: CallbackContext) -> int:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_sprint_common(context, chat_id, message_id)

    async def _ask_sprint_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # If we already have a sprint => skip
        if task_data.sprint_id is not None:
            LOGGER.info(
                "Sprint already set (%s), skipping sprint step.",
                task_data.sprint_id,
            )
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Sprint retained from previous task. Proceeding...",
            )
            return await self._ask_epic_common(context, chat_id, message_id)

        if not user_cfg.sprint.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping sprint. Proceeding to next step...",
            )
            return await self._ask_epic_common(context, chat_id, message_id)

        if user_cfg.sprint.values:
            options = user_cfg.sprint.values
            data = user_cfg.sprint.values
        else:
            active_and_future_sprints = [
                s for s in task_data.sprints if s.state in ("active", "future")
            ]
            if not active_and_future_sprints:
                LOGGER.info("No active or future sprints found.")
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="No active or future sprints found. Proceeding...",
                )
                return await self._ask_epic_common(context, chat_id, message_id)
            options = [s.name for s in active_and_future_sprints]
            data = [str(s.id) for s in active_and_future_sprints]

        reply_markup = self.build_keyboard(options, data, include_skip=True)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose a sprint from the list below:",
            reply_markup=reply_markup,
        )
        return self.SPRINT

    async def add_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            try:
                task_data.sprint_id = int(query.data)
                LOGGER.info("Sprint selected: %s", task_data.sprint_id)
            except ValueError:
                LOGGER.info("Sprint selected (custom string): %s", query.data)
                task_data.sprint_id = None
        else:
            LOGGER.info("Sprint skipped.")

        return await self.ask_epic_from_query(query, context)

    # -------------------------------------------------------------------------
    #  EPIC
    # -------------------------------------------------------------------------
    async def ask_epic_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_epic_common(context, chat_id, message_id)

    async def _ask_epic_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # If epic is already set => skip
        if task_data.epic_link:
            LOGGER.info(
                "Epic already set (%s), skipping epic step.",
                task_data.epic_link,
            )
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Epic retained from previous task. Proceeding...",
            )
            return await self._ask_release_common(context, chat_id, message_id)

        if not user_cfg.epic_link.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping epic link. Proceeding to the next step...",
            )
            return await self._ask_release_common(context, chat_id, message_id)

        if user_cfg.epic_link.values:
            options = user_cfg.epic_link.values
            data = user_cfg.epic_link.values
        else:
            if not task_data.epics:
                LOGGER.info("No epics found for %s", task_data.project_key)
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="No epics found. Proceeding...",
                )
                return await self._ask_release_common(context, chat_id, message_id)
            options = [epic.fields.summary for epic in task_data.epics]
            data = [epic.key for epic in task_data.epics]

        reply_markup = self.build_keyboard(
            options,
            data,
            include_skip=True,
            row_width=3,
        )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose an epic from the list below:",
            reply_markup=reply_markup,
        )
        return self.EPIC

    async def add_epic(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.epic_link = query.data
        else:
            LOGGER.info("Epic skipped.")
        LOGGER.info("Epic selected: %s", task_data.epic_link)

        return await self.ask_release_from_query(query, context)

    # -------------------------------------------------------------------------
    #  RELEASE
    # -------------------------------------------------------------------------
    async def ask_release_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_release_common(context, chat_id, message_id)

    async def _ask_release_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # If release is already set => skip
        if task_data.release:
            LOGGER.info(
                "Release already set (%s), skipping release step.",
                task_data.release,
            )
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Release retained from previous task. Proceeding...",
            )
            return await self._ask_task_type_common(context, chat_id, message_id)

        if not user_cfg.release.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping release. Proceeding to next step...",
            )
            return await self._ask_task_type_common(context, chat_id, message_id)

        if user_cfg.release.values:
            options = user_cfg.release.values
        else:
            releases = [
                v
                for v in self.jira_repository.get_project_versions(
                    task_data.project_key,
                )
                if not v.released
            ]
            if not releases:
                LOGGER.info("No unreleased versions found.")
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="No unreleased versions found. Proceeding...",
                )
                return await self._ask_task_type_common(context, chat_id, message_id)
            options = [version.name for version in releases]

        reply_markup = self.build_keyboard(options, include_skip=True, row_width=3)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose a release from the list below:",
            reply_markup=reply_markup,
        )
        return self.RELEASE

    async def add_release(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.release = query.data
            LOGGER.info("Release selected: %s", task_data.release)
        else:
            LOGGER.info("Release skipped.")

        return await self.ask_task_type_from_query(query, context)

    # -------------------------------------------------------------------------
    #  TASK TYPE
    # -------------------------------------------------------------------------
    async def ask_task_type_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_task_type_common(context, chat_id, message_id)

    async def _ask_task_type_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # If task_type already set => skip
        if task_data.task_type:
            LOGGER.info(
                "Task type already set (%s), skipping step.",
                task_data.task_type,
            )
            # If it's sub-task, we might need to ask for parent story
            if task_data.task_type.lower() == "sub-task":
                return await self._maybe_ask_for_subtask_story(
                    context,
                    chat_id,
                    message_id,
                )
            else:
                return await self._ask_story_points_common(context, chat_id, message_id)

        if not user_cfg.task_type.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping task type. Proceeding to the next step...",
            )
            return await self._ask_story_points_common(context, chat_id, message_id)

        if user_cfg.task_type.values:
            options = user_cfg.task_type.values
        else:
            options = task_data.task_types

        reply_markup = self.build_keyboard(options, row_width=3)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose a task type from the list below:",
            reply_markup=reply_markup,
        )
        return self.TASK_TYPE

    async def add_task_type(self, update: Update, context: CallbackContext) -> int:
        """If user selects sub-task, we ask for the parent story; else go on."""
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        task_data.task_type = query.data
        LOGGER.info("Task type selected: %s", task_data.task_type)

        if task_data.task_type.lower() == "sub-task":
            return await self._maybe_ask_for_subtask_story(
                context,
                query.message.chat_id,
                query.message.message_id,
            )
        else:
            return await self._ask_story_points_common(
                context,
                query.message.chat_id,
                query.message.message_id,
            )

    async def _maybe_ask_for_subtask_story(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """
        If sub-task is selected but the user already has parent_issue_key
        from keep-fields, skip. Otherwise, ask which story should be the parent.
        """
        task_data: TaskData = context.user_data["task_data"]

        if task_data.parent_issue_key:
            LOGGER.info(
                "Sub-task story already set (%s). Skipping selection.",
                task_data.parent_issue_key,
            )
            # Remove epic from sub-task
            task_data.epic_link = None
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Sub-task story retained from previous task. Proceeding...",
            )
            return await self._ask_story_points_common(context, chat_id, message_id)

        # Otherwise ask for parent story
        return await self.ask_subtask_story(chat_id, message_id, context)

    # -------------------------------------------------------------------------
    #  SUB-TASK: SELECT PARENT STORY
    # -------------------------------------------------------------------------
    async def ask_subtask_story(
        self,
        chat_id: int,
        message_id: int,
        context: CallbackContext,
    ) -> int:
        """List stories in the chosen epic if epic_link is set, else all stories in the project."""
        task_data: TaskData = context.user_data["task_data"]
        if task_data.epic_link:
            stories = self.jira_repository.get_stories_by_epic(
                project_key=task_data.project_key,
                epic_key=task_data.epic_link,
            )
        else:
            stories = self.jira_repository.get_stories_by_project(
                task_data.project_key,
            )

        if not stories:
            LOGGER.info(
                "No stories found for sub-task creation. Skipping parent story.",
            )
            task_data.epic_link = None
            return await self._ask_story_points_common(context, chat_id, message_id)

        story_texts = []
        story_data = []
        for s in stories:
            story_texts.append(s.fields.summary)
            story_data.append(s.key)

        reply_markup = self.build_keyboard(
            options=story_texts,
            data=story_data,
            row_width=3,
        )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                "Since you selected a sub-task, please choose the parent Story.\n"
                "(Stories listed in the chosen epic if any, else all project stories.)"
            ),
            reply_markup=reply_markup,
        )
        return self.SELECT_STORY

    async def add_subtask_story(self, update: Update, context: CallbackContext) -> int:
        """
        The user picked which story is the parent. Then remove epic from final data
        because sub-tasks can't have an epic.
        """
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        task_data.parent_issue_key = query.data
        LOGGER.info("Sub-task parent story: %s", task_data.parent_issue_key)

        task_data.epic_link = None  # remove epic for sub-tasks
        return await self._ask_story_points_common(
            context,
            query.message.chat_id,
            query.message.message_id,
        )

    # -------------------------------------------------------------------------
    #  STORY POINTS
    # -------------------------------------------------------------------------
    async def _ask_story_points_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        if task_data.story_points is not None:
            LOGGER.info(
                "Story points already set (%s), skipping step.",
                task_data.story_points,
            )
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Story points retained from previous task. Proceeding...",
            )
            return await self._ask_deadline_common(context, chat_id, message_id)

        if not user_cfg.story_point.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping story points. Proceeding to the next step...",
            )
            return await self._ask_deadline_common(context, chat_id, message_id)

        if user_cfg.story_point.values:
            options = user_cfg.story_point.values
        else:
            options = [str(sp) for sp in self.STORY_POINTS_VALUES]

        reply_markup = self.build_keyboard(options, include_skip=True, row_width=3)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Got it! Now choose the story points:",
            reply_markup=reply_markup,
        )
        return self.STORY_POINTS

    async def add_story_points(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            try:
                task_data.story_points = float(query.data)
            except ValueError:
                LOGGER.info("User picked a non-numeric story point: %s", query.data)
                task_data.story_points = None
        LOGGER.info("Story points selected: %s", task_data.story_points)

        return await self._ask_deadline_common(
            context,
            query.message.chat_id,
            query.message.message_id,
        )

    # -------------------------------------------------------------------------
    #  DEADLINE
    # -------------------------------------------------------------------------
    async def _ask_deadline_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        if task_data.due_date is not None:
            LOGGER.info("Deadline already set (%s), skipping step.", task_data.due_date)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Deadline retained from previous task. Proceeding...",
            )
            return await self._ask_labels_common(context, chat_id, message_id)

        if not user_cfg.deadline.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping deadline. Proceeding to the next step...",
            )
            return await self._ask_labels_common(context, chat_id, message_id)

        days_text = [item[1] for item in self.DEADLINE_OPTIONS]
        days_data = [item[0] for item in self.DEADLINE_OPTIONS]
        reply_markup = self.build_keyboard(
            days_text,
            days_data,
            include_skip=True,
            row_width=3,
        )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Please pick the number of days until the deadline (or skip):",
            reply_markup=reply_markup,
        )
        return self.DEADLINE

    async def add_deadline(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]

        if query.data.lower() == "skip":
            LOGGER.info("Deadline skipped.")
            task_data.due_date = None
            task_data.target_end = None
        else:
            try:
                day_offset = int(query.data)
                target_date = datetime.date.today() + datetime.timedelta(
                    days=day_offset,
                )
                date_str = target_date.strftime("%Y-%m-%d")
                task_data.due_date = date_str
                task_data.target_end = date_str
                LOGGER.info(
                    "Deadline chosen: day offset %s => %s",
                    day_offset,
                    date_str,
                )
            except ValueError:
                LOGGER.warning("Invalid day offset picked: %s", query.data)
                task_data.due_date = None
                task_data.target_end = None

        return await self._ask_labels_common(
            context,
            query.message.chat_id,
            query.message.message_id,
        )

    # -------------------------------------------------------------------------
    #  LABELS
    # -------------------------------------------------------------------------
    async def _ask_labels_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

        # If labels exist => skip
        if task_data.labels:
            LOGGER.info("Labels already exist (%s), skipping step.", task_data.labels)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Labels retained from previous task. Proceeding to attachments...",
            )
            return await self._ask_attachment_prompt(context, chat_id, message_id)

        if not user_cfg.labels.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping labels. Proceeding to attachments...",
            )
            return await self._ask_attachment_prompt(context, chat_id, message_id)

        if user_cfg.labels.values:
            all_labels = user_cfg.labels.values
        else:
            all_labels = []

        context.user_data["available_labels"] = all_labels
        task_data.labels = []

        reply_markup = self.build_label_selection_keyboard(
            all_labels=all_labels,
            selected=task_data.labels,
        )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                "Choose one or more labels (toggle on/off). "
                "Press 'New Label' to define a new one, 'Done' when finished, or 'Skip'."
            ),
            reply_markup=reply_markup,
        )
        return self.LABELS

    async def toggle_label_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        available_labels = context.user_data.get("available_labels", [])

        data = query.data
        if data.startswith("lbl|"):
            label_name = data.split("|", 1)[1]
            if label_name in task_data.labels:
                task_data.labels.remove(label_name)
            else:
                task_data.labels.append(label_name)

            reply_markup = self.build_label_selection_keyboard(
                all_labels=available_labels,
                selected=task_data.labels,
            )
            await query.edit_message_text(
                text="Toggle labels, or use 'New Label', then 'Done' or 'Skip'.",
                reply_markup=reply_markup,
            )
            return self.LABELS

        elif data == "lbl_new":
            await query.edit_message_text("Please type your new label:")
            return self.LABELS_NEW

        elif data == "lbl_done":
            LOGGER.info("Labels selected: %s", task_data.labels)
            return await self._ask_attachment_prompt(
                context,
                query.message.chat_id,
                query.message.message_id,
            )

        elif data == "skip":
            task_data.labels = []
            LOGGER.info("Label selection skipped.")
            return await self._ask_attachment_prompt(
                context,
                query.message.chat_id,
                query.message.message_id,
            )

        return self.LABELS

    async def add_new_label(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        available_labels = context.user_data.get("available_labels", [])

        new_label = update.message.text.strip()
        if new_label not in available_labels:
            available_labels.append(new_label)
        if new_label not in task_data.labels:
            task_data.labels.append(new_label)

        reply_markup = self.build_label_selection_keyboard(
            all_labels=available_labels,
            selected=task_data.labels,
        )
        await update.message.reply_text(
            "Label added. Toggle any others, or 'New Label' again, or 'Done'/'Skip'.",
            reply_markup=reply_markup,
        )
        return self.LABELS

    # -------------------------------------------------------------------------
    #  ATTACHMENTS
    # -------------------------------------------------------------------------
    async def _ask_attachment_prompt(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        user_cfg = context.user_data["user_config"]
        # Typically we don't "keep" attachments, but you could if desired.

        if not user_cfg.attachment.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping attachments. Creating the task...",
            )
            chat_obj = await context.bot.send_message(chat_id, "Creating your task...")
            await self.finalize_task(chat_obj, context)
            return self.CREATE_ANOTHER

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                "Got it! Now you can send attachments (images, videos, documents). "
                "When you're done, type 'done' or 'skip' to skip attachments."
            ),
        )
        return self.ATTACHMENT

    async def add_attachment(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        attachments = task_data.attachments
        media_group_messages = context.user_data.setdefault("media_group_messages", {})

        if update.message.text:
            txt = update.message.text.lower()
            if txt == "skip":
                LOGGER.info("User skipped attachments.")
                for msgs in media_group_messages.values():
                    await self.process_media_group(msgs, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return self.CREATE_ANOTHER
            elif txt == "done":
                LOGGER.info("User finished attachments.")
                for msgs in media_group_messages.values():
                    await self.process_media_group(msgs, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return self.CREATE_ANOTHER
            else:
                await update.message.reply_text(
                    "Invalid input. Please type 'done' or 'skip'.",
                )
                return self.ATTACHMENT

        # If media_group_id is set, we collect them for a single group
        if update.message.media_group_id:
            msgs = media_group_messages.setdefault(update.message.media_group_id, [])
            msgs.append(update.message)
            return self.ATTACHMENT
        elif any(
            [
                update.message.photo,
                update.message.video,
                update.message.audio,
                update.message.document,
            ],
        ):
            await self.process_single_media(update.message, attachments)
            await update.message.reply_text(
                "Attachment received. You can send more, or 'done' to finish.",
            )
            return self.ATTACHMENT
        else:
            await update.message.reply_text(
                "Please upload an attachment or type 'done'/'skip'.",
            )
            return self.ATTACHMENT

    async def process_media_group(
        self,
        messages: List[Any],
        attachments: Dict[str, List],
    ):
        async with aiohttp.ClientSession() as session:
            for idx, media_message in enumerate(messages):
                if media_message.photo:
                    await self.fetch_and_store_media(
                        media_message.photo[-1],
                        session,
                        attachments["images"],
                        f"image_{idx}.jpg",
                    )
                elif media_message.document:
                    await self.fetch_and_store_media(
                        media_message.document,
                        session,
                        attachments["documents"],
                        media_message.document.file_name,
                    )
                elif media_message.video:
                    await self.fetch_and_store_media(
                        media_message.video,
                        session,
                        attachments["videos"],
                        f"video_{idx}.mp4",
                    )
                elif media_message.audio:
                    await self.fetch_and_store_media(
                        media_message.audio,
                        session,
                        attachments["audio"],
                        f"audio_{idx}.mp3",
                    )

    async def process_single_media(self, message: Any, attachments: Dict[str, List]):
        async with aiohttp.ClientSession() as session:
            if message.photo:
                await self.fetch_and_store_media(
                    message.photo[-1],
                    session,
                    attachments["images"],
                    "single_image.jpg",
                )
            elif message.video:
                await self.fetch_and_store_media(
                    message.video,
                    session,
                    attachments["videos"],
                    "video.mp4",
                )
            elif message.audio:
                await self.fetch_and_store_media(
                    message.audio,
                    session,
                    attachments["audio"],
                    "audio.mp3",
                )
            elif message.document:
                await self.fetch_and_store_media(
                    message.document,
                    session,
                    attachments["documents"],
                    message.document.file_name,
                )

    async def fetch_and_store_media(self, media, session, storage_list, filename):
        media_file = await media.get_file()
        async with session.get(media_file.file_path) as response:
            if response.status == 200:
                buffer = BytesIO(await response.read())
                storage_list.append((filename, buffer))
            else:
                LOGGER.error("Failed to fetch media from %s", media_file.file_path)

    # -------------------------------------------------------------------------
    #  FINALIZE AND CREATE ANOTHER?
    # -------------------------------------------------------------------------
    async def finalize_task(
        self,
        update_or_message: Any,
        context: CallbackContext,
    ) -> None:
        # figure out actual message object
        if hasattr(update_or_message, "message") and update_or_message.message:
            message = update_or_message.message
        else:
            message = update_or_message

        task_data: TaskData = context.user_data["task_data"]
        try:
            new_issue = self.jira_repository.create_task(task_data)
            await message.reply_text(
                f"Task created successfully! Link: {self.jira_repository.settings.domain}/browse/{new_issue.key}",
            )
            assignee_user_data = self.user_config.get_user_config_by_jira_username(
                task_data.assignee,
            )
            if assignee_user_data:
                try:
                    await context.bot.send_message(
                        chat_id=assignee_user_data.telegram_user_chat_id,
                        text=(
                            f"Task \n📄{task_data.summary} "
                            f"\n{self.jira_repository.settings.domain}/browse/{new_issue.key} was created for you"
                        ),
                    )
                except Exception as e:
                    LOGGER.error("Failed to notify user about task creation: %s", e)
        except Exception as e:
            await message.reply_text(f"Failed to create task: {e}")
            return

        # Ask if they want to create another
        reply_markup = self.build_keyboard(
            ["Yes", "Yes, same as before", "No"],
            ["yes", "yes, same as before", "no"],
            row_width=2,
        )
        msg = await message.reply_text(
            "Do you want to create another task **with similar fields**?",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
        context.user_data["last_inline_message_id"] = msg.message_id

    async def handle_create_another(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()

        if query.data == "yes":
            await query.edit_message_text(
                "Please select which fields to keep from the previous task (multi-select).",
            )
            return await self.ask_keep_fields(query, context)
        elif query.data == "yes, same as before":
            old_data: TaskData = context.user_data["task_data"]

            new_data = old_data.model_copy()
            new_data.attachments = {
                "images": [],
                "documents": [],
                "videos": [],
                "audio": [],
            }
            context.user_data["task_data"] = new_data
            await query.edit_message_text(
                "Please enter the task summary for the new issue:",
            )
            return self.SUMMARY
        else:
            await query.edit_message_text("Task Creation Completed!")
            return ConversationHandler.END

    # -------------------------------------------------------------------------
    #  MULTI-SELECT FIELDS TO KEEP
    # -------------------------------------------------------------------------
    def build_keep_fields_keyboard(
        self,
        possible_fields: List[str],
        selected_fields: List[str],
    ) -> InlineKeyboardMarkup:
        """
        Build a toggle keyboard for selecting which fields to keep.
        Show a "✔" if selected. Always add a "Done" and "Skip" at the bottom.
        """
        keyboard = []
        row_width = 2

        for i in range(0, len(possible_fields), row_width):
            row = []
            chunk = possible_fields[i : i + row_width]
            for field in chunk:
                mark = "✔" if field in selected_fields else ""
                btn_text = f"{field} {mark}"
                row.append(
                    InlineKeyboardButton(btn_text, callback_data=f"keep|{field}"),
                )
            keyboard.append(row)

        bottom_row = [
            InlineKeyboardButton("Done", callback_data="keep_done"),
            InlineKeyboardButton("Skip", callback_data="keep_skip"),
        ]
        keyboard.append(bottom_row)

        return InlineKeyboardMarkup(keyboard)

    async def ask_keep_fields(self, update: Update, context: CallbackContext) -> int:
        """
        Present a multi-select list of fields:
         - project
         - sprint
         - epic
         - assignee
         - component
         - label
         - (plus 'story' if the old task was sub-task)
        """
        task_data: TaskData = context.user_data["task_data"]

        fields = ["project", "sprint", "epic", "assignee", "component", "label"]
        if task_data.task_type and task_data.task_type.lower() == "sub-task":
            fields.append("story")

        context.user_data["possible_keep_fields"] = fields
        context.user_data["selected_keep_fields"] = []

        reply_markup = self.build_keep_fields_keyboard(fields, [])
        await update.edit_message_text(
            text="Select which fields you want to keep for the new task:",
            reply_markup=reply_markup,
        )
        return self.KEEP_FIELDS

    async def toggle_keep_field_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()

        data = query.data
        possible_fields = context.user_data["possible_keep_fields"]
        selected_fields = context.user_data["selected_keep_fields"]

        if data.startswith("keep|"):
            field = data.split("|", 1)[1]
            if field in selected_fields:
                selected_fields.remove(field)
            else:
                selected_fields.append(field)

            reply_markup = self.build_keep_fields_keyboard(
                possible_fields,
                selected_fields,
            )
            await query.edit_message_text(
                text="Toggle the fields you want to keep, then 'Done' or 'Skip'.",
                reply_markup=reply_markup,
            )
            return self.KEEP_FIELDS

        elif data == "keep_done":
            return await self._setup_new_task_with_kept_fields(
                query,
                context,
                selected_fields,
            )

        elif data == "keep_skip":
            # skip => keep nothing
            return await self._setup_new_task_with_kept_fields(query, context, [])

        return self.KEEP_FIELDS

    async def _setup_new_task_with_kept_fields(
        self,
        query: CallbackQuery,
        context: CallbackContext,
        selected_fields: List[str],
    ) -> int:
        """
        Build a new TaskData with only the selected fields from the old one.
        Then proceed with summary step again.
        """
        old_data: TaskData = context.user_data["task_data"]

        new_data = TaskData()
        new_data.attachments = {
            "images": [],
            "documents": [],
            "videos": [],
            "audio": [],
        }
        new_data.components = []
        new_data.labels = []

        # Copy over selected fields
        if "project" in selected_fields:
            new_data.project_key = old_data.project_key
            new_data.board_id = old_data.board_id
            new_data.sprints = old_data.sprints
            new_data.task_types = old_data.task_types
            new_data.epics = old_data.epics

        if "sprint" in selected_fields:
            new_data.sprint_id = old_data.sprint_id

        # Always allow epic if user selected it, even if old was sub-task
        if "epic" in selected_fields:
            if old_data.epic_link:
                # If old_data actually has an epic, carry it over
                new_data.epic_link = old_data.epic_link
            else:
                # Old sub-task probably had no epic.
                # Leave new_data.epic_link = None so that the user is prompted
                pass

        if "assignee" in selected_fields:
            new_data.assignee = old_data.assignee

        if (
            "story" in selected_fields
            and old_data.task_type
            and old_data.task_type.lower() == "sub-task"
        ):
            new_data.parent_issue_key = old_data.parent_issue_key
            new_data.task_type = "Sub-task"  # preserve sub-task type as well

        if "component" in selected_fields:
            new_data.components = old_data.components.copy()

        if "label" in selected_fields:
            new_data.labels = old_data.labels.copy()

        # Store new_data as the new "task_data"
        context.user_data["task_data"] = new_data

        # Now ask for summary again
        await query.edit_message_text(
            "Please enter the task summary for the new issue:",
        )
        return self.SUMMARY
