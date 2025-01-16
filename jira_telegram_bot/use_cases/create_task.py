from __future__ import annotations

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
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.authentication import check_user_allowed
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interface.user_config_interface import (
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
        ATTACHMENT,
        ASSIGNEE_SEARCH,
        ASSIGNEE_RESULT,
        CREATE_ANOTHER,
    ) = range(15)

    def __init__(
        self,
        jira_repository: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        self.jira_repository = jira_repository
        self.user_config = user_config
        self.media_group_timeout = 1.0
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]

    def build_keyboard(
        self,
        options: List[str],
        data: Optional[List[str]] = None,
        include_skip: bool = False,
        row_width: int = 2,
        extra_buttons: Optional[List[List[InlineKeyboardButton]]] = None,
    ) -> InlineKeyboardMarkup:
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

    async def start(self, update: Update, context: CallbackContext) -> int:
        """User starts conversation with /super_task."""
        if not await check_user_allowed(update):
            return ConversationHandler.END

        context.user_data.clear()

        task_data = TaskData()
        context.user_data["task_data"] = task_data
        config = self.user_config.get_user_config(update.message.from_user.username)
        context.user_data["user_config"] = config

        projects = self.jira_repository.get_projects()
        options = [project.name for project in projects]
        data = [project.key for project in projects]
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
            message = await update.message.reply_text(
                'Got it! Now send me the description of the task (or type "skip" to skip).',
            )
            context.user_data["last_inline_message_id"] = message.message_id
            return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        """User typed a description or 'skip'. Next: maybe show component step."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]
        if not task_data.description:
            desc = update.message.text.strip()
            if desc.lower() != "skip":
                task_data.description = desc

        last_message_id = context.user_data["last_inline_message_id"]

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

        reply_markup = self.build_keyboard(options, include_skip=True)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=last_message_id,
            text="Got it! Now choose a component from the list below:",
            reply_markup=reply_markup,
        )
        return self.COMPONENT

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        """User clicked on a component or skipped it."""
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.component = query.data
        LOGGER.info("Component selected: %s", task_data.component)
        return await self.ask_assignee(query, context)

    async def ask_assignee_from_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Called if we skip component from a text-based flow."""
        last_message_id = context.user_data["last_inline_message_id"]
        return await self._ask_assignee_common(
            context,
            update.effective_chat.id,
            last_message_id,
        )

    async def ask_assignee(self, query: CallbackQuery, context: CallbackContext) -> int:
        """Called if we come from an inline button to show assignee next."""
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_assignee_common(context, chat_id, message_id)

    async def _ask_assignee_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """Helper to ask user to pick an assignee, or skip if turned off."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

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
        """User picks assignee or 'others' or skip."""
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
        """User typed 'others' search string."""
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
        """User picks from the search result or 'others' or skip."""
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

    async def ask_priority_from_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Helper if we come from a text-based function to set priority."""
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
        """Internal helper used if skipping from text-based steps."""
        return await self._ask_priority_common(context, chat_id, message_id)

    async def ask_priority_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        """Helper if we come from an inline button to set priority."""
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_priority_common(context, chat_id, message_id)

    async def _ask_priority_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """Check user config for priority, skip or show the inline keyboard."""
        user_cfg = context.user_data["user_config"]

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
        """User picks a priority or skip."""
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.priority = query.data
        LOGGER.info("Priority selected: %s", task_data.priority)

        return await self.ask_sprint(query, context)

    async def ask_sprint(self, query: CallbackQuery, context: CallbackContext) -> int:
        """Display sprints or skip if user config says so."""
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_sprint_common(context, chat_id, message_id)

    async def _ask_sprint_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """Check user config for sprint, skip or show sprints."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

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
        """User picks sprint or skip."""
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

    async def ask_epic_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        """Ask epic or skip if not set_field."""
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return await self._ask_epic_common(context, chat_id, message_id)

    async def _ask_epic_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """Show epic or skip if user config says so."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

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
        """User picks epic or skip."""
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.epic_link = query.data
        else:
            LOGGER.info("Epic skipped.")
        LOGGER.info("Epic selected: %s", task_data.epic_link)

        return await self.ask_release_from_query(query, context)

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
        """Show release or skip."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

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
        """User picks release or skip."""
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.release = query.data
            LOGGER.info("Release selected: %s", task_data.release)
        else:
            LOGGER.info("Release skipped.")

        return await self.ask_task_type_from_query(query, context)

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
        """Show task type or skip if user config says so."""
        task_data: TaskData = context.user_data["task_data"]
        user_cfg = context.user_data["user_config"]

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
        """User picks or skip."""
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        task_data.task_type = query.data
        LOGGER.info("Task type selected: %s", task_data.task_type)

        return await self._ask_story_points_common(
            context,
            query.message.chat_id,
            query.message.message_id,
        )

    async def _ask_story_points_common(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """Show or skip story points."""
        user_cfg = context.user_data["user_config"]

        if not user_cfg.story_point.set_field:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Skipping story points. Proceeding to attachments...",
            )
            return await self._ask_attachment_prompt(context, chat_id, message_id)

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
        """User picks story points or skip."""
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

        return await self._ask_attachment_prompt(
            context,
            query.message.chat_id,
            query.message.message_id,
        )

    async def _ask_attachment_prompt(
        self,
        context: CallbackContext,
        chat_id: int,
        message_id: int,
    ) -> int:
        """Show or skip attachments based on user config."""
        user_cfg = context.user_data["user_config"]

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
        """Handles user sending attachments or typing 'done'/'skip'."""
        task_data: TaskData = context.user_data["task_data"]
        attachments = task_data.attachments
        media_group_messages = context.user_data.setdefault("media_group_messages", {})

        if update.message.text:
            if update.message.text.lower() == "skip":
                LOGGER.info("User skipped attachments.")
                for msgs in media_group_messages.values():
                    await self.process_media_group(msgs, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return self.CREATE_ANOTHER
            elif update.message.text.lower() == "done":
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
        """Downloads each item in a media group."""
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
        """Download a single piece of media."""
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
        """GET the file contents from Telegram, store in memory."""
        media_file = await media.get_file()
        async with session.get(media_file.file_path) as response:
            if response.status == 200:
                buffer = BytesIO(await response.read())
                storage_list.append((filename, buffer))
            else:
                LOGGER.error("Failed to fetch media from %s", media_file.file_path)

    async def finalize_task(
        self,
        update_or_message: Any,
        context: CallbackContext,
    ) -> None:
        """
        Actually create the ticket in JIRA and ask user if they want to create another.
        We can handle `update_or_message` if we might be calling this from a pure message object.
        """
        if hasattr(update_or_message, "message") and update_or_message.message:
            message = update_or_message.message
        else:
            message = update_or_message

        task_data: TaskData = context.user_data["task_data"]
        try:
            new_issue = self.jira_repository.create_task(task_data)
            await message.reply_text(
                f"Task created successfully! Link: {JIRA_SETTINGS.domain}/browse/{new_issue.key}",
            )
            assignee_user_data = self.user_config.get_user_config_by_jira_username(
                task_data.assignee,
            )
            if assignee_user_data:
                try:
                    await context.bot.send_message(
                        chat_id=assignee_user_data.telegram_user_chat_id,
                        text=f"Task  {JIRA_SETTINGS.domain}/browse/{new_issue.key} was created for you",
                    )
                except Exception as e:
                    LOGGER.error("Failed to notify user about task creation: %s", e)
        except Exception as e:
            await message.reply_text(f"Failed to create task: {e}")
            return

        reply_markup = self.build_keyboard(["Yes", "No"], ["yes", "no"], row_width=2)
        msg = await message.reply_text(
            "Do you want to create another task with similar fields?",
            reply_markup=reply_markup,
        )
        context.user_data["last_inline_message_id"] = msg.message_id

    async def handle_create_another(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """User picks 'Yes' or 'No' after successful creation."""
        query = update.callback_query
        await query.answer()
        if query.data == "yes":
            task_data: TaskData = context.user_data["task_data"]
            task_data.summary = None
            task_data.description = None
            task_data.story_points = None
            task_data.attachments = {
                "images": [],
                "documents": [],
                "videos": [],
                "audio": [],
            }
            await query.edit_message_text("Please enter the task summary:")
            return self.SUMMARY
        else:
            await query.edit_message_text("Task Creation Completed!")
            return ConversationHandler.END
