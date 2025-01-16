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

    def __init__(self, jira_repository: TaskManagerRepositoryInterface):
        self.jira_repository = jira_repository
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]
        self.media_group_timeout = 1.0

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
        """
        User starts the conversation with /super_task.
        We ask the user to choose a Jira project from an inline keyboard.
        """
        if not await check_user_allowed(update):
            return ConversationHandler.END

        # Clear any stored conversation data
        context.user_data.clear()
        task_data = TaskData()
        context.user_data["task_data"] = task_data

        projects = self.jira_repository.get_projects()
        options = [project.name for project in projects]
        data = [project.key for project in projects]
        reply_markup = self.build_keyboard(options, data, row_width=3)

        message = await update.message.reply_text(
            "Please select a project from the list below:",
            reply_markup=reply_markup,
        )
        # We store the ID of the message that has the inline keyboard we want to keep editing.
        context.user_data["last_inline_message_id"] = message.message_id

        return self.PROJECT

    async def select_project(self, update: Update, context: CallbackContext) -> int:
        """
        The user clicked on one of the project buttons.
        We store the project and ask them to type the summary (this is text, not inline keyboard).
        """
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

        # We don't need to update the inline keyboard message here. Instead,
        # we delete the keyboard from the project selection message:
        await query.edit_message_text(text="Please enter the task summary:")

        return self.SUMMARY

    async def add_summary(self, update: Update, context: CallbackContext) -> int:
        """
        User sent a summary message. We store it and ask for a description by normal text message.
        """
        task_data: TaskData = context.user_data["task_data"]
        message = update.message

        # For demonstration, let's keep your existing logic
        if message.forward and message.forward_origin:
            text = message.text or message.caption or ""
            lines = text.strip().split("\n")
            task_data.summary = lines[0] if lines else ""
            task_data.description = text
            LOGGER.info("Summary from forwarded message: %s", task_data.summary)
            # handle attachments if present
            attachments = task_data.attachments
            if any([message.photo, message.video, message.document, message.audio]):
                await self.process_single_media(message, attachments)

            await update.message.reply_text("Got it! Proceeding to the next step.")
            return self.DESCRIPTION
        else:
            # Normal text (not forwarded)
            task_data.summary = message.text.strip()
            LOGGER.info("Summary received: %s", task_data.summary)
            await update.message.reply_text(
                'Got it! Now send me the description of the task (or type "skip" to skip).',
            )
            return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        """
        User typed the description or 'skip'.
        Next step: show inline keyboard for 'components', but do it by editing
        the same last-inline message.
        """
        task_data: TaskData = context.user_data["task_data"]
        if not task_data.description:
            description = update.message.text.strip()
            if description.lower() != "skip":
                task_data.description = description

        # Next: build the inline keyboard for Components
        components = self.jira_repository.get_project_components(task_data.project_key)
        if components:
            options = [component.name for component in components]
            reply_markup = self.build_keyboard(options, include_skip=True)

            # We need to edit the *existing* inline-keyboard message. But the last
            # inline keyboard message was from PROJECT selection. We can reuse that same
            # message ID.
            last_message_id = context.user_data["last_inline_message_id"]

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="Got it! Now choose a component from the list below:",
                reply_markup=reply_markup,
            )
            return self.COMPONENT
        else:
            LOGGER.info("No components found for project %s", task_data.project_key)
            # Instead of sending a new message, let's also just update the last one.
            # But we need to say that there's nothing to pick. Then move on to ask_assignee
            last_message_id = context.user_data["last_inline_message_id"]
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="No components found. Proceeding to the next step...",
            )
            return await self.ask_assignee_from_text(update, context)

    async def ask_assignee_from_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        Just a helper to keep code simpler: we want to jump to the assignee step,
        which also edits the last inline keyboard message to show the new options.
        """
        task_data: TaskData = context.user_data["task_data"]
        assignees = self.jira_repository.get_assignees(task_data.project_key)

        last_message_id = context.user_data["last_inline_message_id"]

        if assignees:
            options = assignees
            data = assignees
            extra_buttons = [[InlineKeyboardButton("Others", callback_data="others")]]
            reply_markup = self.build_keyboard(
                options,
                data,
                row_width=2,
                include_skip=True,
                extra_buttons=extra_buttons,
            )
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="Got it! Now choose an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE
        else:
            LOGGER.info("No assignees found for project %s", task_data.project_key)
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=last_message_id,
                text="No assignees found. Proceeding to the next step...",
            )
            return await self.ask_priority_from_text(update, context)

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        """
        The user clicked on a component (inline keyboard).
        We store the chosen component, then ask for assignee by editing the same message.
        """
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.component = query.data

        LOGGER.info("Component selected: %s", task_data.component)
        return await self.ask_assignee(query, context)

    async def ask_assignee(self, query: CallbackQuery, context: CallbackContext) -> int:
        """
        Ask user to pick an assignee from the inline keyboard.
        """
        task_data: TaskData = context.user_data["task_data"]
        assignees = self.jira_repository.get_assignees(task_data.project_key)
        if assignees:
            options = assignees
            data = assignees
            extra_buttons = [[InlineKeyboardButton("Others", callback_data="others")]]
            reply_markup = self.build_keyboard(
                options,
                data,
                row_width=2,
                include_skip=True,
                extra_buttons=extra_buttons,
            )
            # Edit the same message:
            await query.edit_message_text(
                text="Got it! Now choose an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE
        else:
            LOGGER.info("No assignees found for project %s", task_data.project_key)
            await query.edit_message_text(
                text="No assignees found. Proceeding to the next step...",
            )
            return await self.ask_priority_from_query(query, context)

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
        """
        User typed the 'username to search for' when they clicked 'Others'.
        We'll look up possible matches, then show them in an inline keyboard by editing the same message.
        """
        username_query = update.message.text.strip()
        matching_users = self.jira_repository.search_users(username_query)

        # Reuse the last inline keyboard message ID:
        last_message_id = context.user_data["last_inline_message_id"]

        if matching_users:
            options = matching_users
            data = matching_users
            extra_buttons = [[InlineKeyboardButton("Others", callback_data="others")]]
            reply_markup = self.build_keyboard(
                options=options,
                data=data,
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
            # Next message from user is again a TEXT message for the same search
            return self.ASSIGNEE_SEARCH

    async def select_assignee_from_search(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        User clicked on one of the matching assignees from search, or 'Others', or 'skip'.
        """
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data == "others":
            # Prompt user to enter a new username
            await query.edit_message_text("Please enter the username to search for:")
            return self.ASSIGNEE_SEARCH
        elif query.data == "skip":
            task_data.assignee = None
            LOGGER.info("Assignee skipped.")
            return await self.ask_priority_from_query(query, context)
        else:
            # User picked one from the search results
            task_data.assignee = query.data
            LOGGER.info("Assignee selected from search: %s", task_data.assignee)
            return await self.ask_priority_from_query(query, context)

    async def ask_priority_from_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        Helper when we come from a text update. Must edit the last inline keyboard message.
        """
        last_message_id = context.user_data["last_inline_message_id"]
        priorities = self.jira_repository.get_priorities()
        options = [priority.name for priority in priorities]
        reply_markup = self.build_keyboard(options, include_skip=True, row_width=4)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=last_message_id,
            text="Got it! Now choose a priority from the list below:",
            reply_markup=reply_markup,
        )
        return self.PRIORITY

    async def ask_priority_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        """
        Helper to ask priority after an inline-button click.
        """
        priorities = self.jira_repository.get_priorities()
        options = [priority.name for priority in priorities]
        reply_markup = self.build_keyboard(options, include_skip=True, row_width=4)
        await query.edit_message_text(
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

    async def ask_sprint(self, query: CallbackQuery, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        active_and_future_sprints = [
            sprint
            for sprint in task_data.sprints
            if sprint.state in ("active", "future")
        ]

        if active_and_future_sprints:
            options = [sprint.name for sprint in active_and_future_sprints]
            data = [str(sprint.id) for sprint in active_and_future_sprints]
            reply_markup = self.build_keyboard(options, data, include_skip=True)
            await query.edit_message_text(
                text="Got it! Now choose a sprint from the list below:",
                reply_markup=reply_markup,
            )
            return self.SPRINT
        else:
            LOGGER.info("No active or future sprints found.")
            await query.edit_message_text(
                text="No active or future sprints found. Proceeding to the next step...",
            )
            return await self.ask_epic_from_query(query, context)

    async def add_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.sprint_id = int(query.data)
            LOGGER.info("Sprint selected: %s", task_data.sprint_id)
        else:
            LOGGER.info("Sprint skipped.")

        return await self.ask_epic_from_query(query, context)

    async def ask_epic_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        """
        Prompt the user to pick an epic. We do it by editing the same message with the epic keyboard.
        """
        task_data: TaskData = context.user_data["task_data"]
        if task_data.epics:
            options = [epic.fields.summary for epic in task_data.epics]
            data = [epic.key for epic in task_data.epics]
            reply_markup = self.build_keyboard(
                options,
                data,
                include_skip=True,
                row_width=3,
            )
            await query.edit_message_text(
                text="Got it! Now choose an epic from the list below:",
                reply_markup=reply_markup,
            )
            return self.EPIC
        else:
            LOGGER.info("No epics found for project %s", task_data.project_key)
            await query.edit_message_text(
                text="No epics found. Proceeding to the next step...",
            )
            return await self.ask_release_from_query(query, context)

    async def add_epic(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.epic_link = query.data
            LOGGER.info("Epic selected: %s", task_data.epic_link)
        else:
            LOGGER.info("Epic skipped.")

        return await self.ask_release_from_query(query, context)

    async def ask_release_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        task_data: TaskData = context.user_data["task_data"]
        releases = [
            version
            for version in self.jira_repository.get_project_versions(
                task_data.project_key,
            )
            if not version.released
        ]

        if releases:
            options = [version.name for version in releases]
            reply_markup = self.build_keyboard(options, include_skip=True, row_width=3)
            await query.edit_message_text(
                text="Got it! Now choose a release from the list below:",
                reply_markup=reply_markup,
            )
            return self.RELEASE
        else:
            LOGGER.info("No unreleased versions found.")
            await query.edit_message_text(
                text="No unreleased versions found. Proceeding to the next step...",
            )
            return await self.ask_task_type_from_query(query, context)

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

    async def ask_task_type_from_query(
        self,
        query: CallbackQuery,
        context: CallbackContext,
    ) -> int:
        """
        Show the user a list of task types.
        """
        task_data: TaskData = context.user_data["task_data"]
        options = task_data.task_types
        reply_markup = self.build_keyboard(options, row_width=3)
        await query.edit_message_text(
            text="Got it! Now choose a task type from the list below:",
            reply_markup=reply_markup,
        )
        return self.TASK_TYPE

    async def add_task_type(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        task_data.task_type = query.data
        LOGGER.info("Task type selected: %s", task_data.task_type)

        options = [str(sp) for sp in self.STORY_POINTS_VALUES]
        reply_markup = self.build_keyboard(options, include_skip=True, row_width=3)

        await query.edit_message_text(
            text="Got it! Now choose the story points:",
            reply_markup=reply_markup,
        )
        return self.STORY_POINTS

    async def add_story_points(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.story_points = float(query.data)
            LOGGER.info("Story points selected: %s", task_data.story_points)
        else:
            LOGGER.info("Story points skipped.")

        await query.edit_message_text(
            text=(
                "Got it! Now you can send attachments (images, videos, documents). "
                "When you're done, type 'done' or 'skip' to skip attachments."
            ),
        )
        return self.ATTACHMENT

    async def add_attachment(self, update: Update, context: CallbackContext) -> int:
        """
        This part you probably want as separate messages, so that's normal.
        """
        task_data: TaskData = context.user_data["task_data"]
        attachments = task_data.attachments
        media_group_messages = context.user_data.setdefault("media_group_messages", {})

        # Same logic as you had before ...
        if update.message.text:
            if update.message.text.lower() == "skip":
                LOGGER.info("User chose to skip attachment upload.")
                for msgs in media_group_messages.values():
                    await self.process_media_group(msgs, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return self.CREATE_ANOTHER
            elif update.message.text.lower() == "done":
                LOGGER.info("User finished uploading attachments.")
                for msgs in media_group_messages.values():
                    await self.process_media_group(msgs, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return self.CREATE_ANOTHER
            else:
                await update.message.reply_text(
                    "Invalid input. Please type 'done' when finished or 'skip' to skip attachments.",
                )
                return self.ATTACHMENT

        if update.message.media_group_id:
            msgs = media_group_messages.setdefault(
                update.message.media_group_id,
                [],
            )
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
                "Attachment received. You can send more, or type 'done' to finish.",
            )
            return self.ATTACHMENT
        else:
            await update.message.reply_text(
                "Please upload an attachment or type 'done' when finished.",
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
                LOGGER.error(f"Failed to fetch media from {media_file.file_path}")

    async def finalize_task(self, update: Update, context: CallbackContext) -> None:
        """
        Actually create the ticket in JIRA and ask if user wants to create another.
        """
        task_data: TaskData = context.user_data["task_data"]
        try:
            new_issue = self.jira_repository.create_task(task_data)
            await update.message.reply_text(
                f"Task created successfully! Link: {JIRA_SETTINGS.domain}/browse/{new_issue.key}",
            )
        except Exception as e:
            error_message = f"Failed to create task: {e}"
            await update.message.reply_text(error_message)
            return

        # Offer to create another. We'll do this by a quick inline keyboard in a new message:
        reply_markup = self.build_keyboard(["Yes", "No"], ["yes", "no"], row_width=2)
        msg = await update.message.reply_text(
            "Do you want to create another task with similar fields?",
            reply_markup=reply_markup,
        )
        # Store this new inline keyboard's message ID if you want to keep editing it as well:
        context.user_data["last_inline_message_id"] = msg.message_id

    async def handle_create_another(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "yes":
            task_data: TaskData = context.user_data["task_data"]
            # Reset relevant fields:
            task_data.summary = None
            task_data.description = None
            task_data.story_points = None
            task_data.attachments = {
                "images": [],
                "documents": [],
                "videos": [],
                "audio": [],
            }
            # Re-use the same conversation.
            await query.edit_message_text("Please enter the task summary:")
            return self.SUMMARY
        else:
            await query.edit_message_text("Task Creation Completed!")
            return ConversationHandler.END
