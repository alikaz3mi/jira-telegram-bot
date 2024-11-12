from __future__ import annotations

from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import aiohttp
from jira import Issue
from jira import JIRA
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.authentication import check_user_allowed


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
    ) = range(14)

    def __init__(self, jira_client: JIRA):
        self.jira_client = jira_client
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]
        self.media_group_timeout = 1.0

    async def start(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        context.user_data.clear()
        task_data = TaskData()
        context.user_data["task_data"] = task_data

        projects = self.jira_client.projects()
        keyboard = [
            [
                InlineKeyboardButton(project.name, callback_data=project.key)
                for project in projects[i : i + 2]
            ]
            for i in range(0, len(projects), 2)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Please select a project from the list below:",
            reply_markup=reply_markup,
        )
        return self.PROJECT

    async def select_project(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        project_key = query.data
        task_data: TaskData = context.user_data["task_data"]
        task_data.project_key = project_key

        LOGGER.info("Project selected: %s", project_key)

        task_data.epics = self._get_epics(project_key)
        task_data.board_id = self._get_board_id(project_key)
        task_data.sprints = (
            self.jira_client.sprints(board_id=task_data.board_id)
            if task_data.board_id
            else []
        )
        task_data.task_types = [
            z.name for z in self.jira_client.issue_types_for_project(project_key)
        ]

        await query.edit_message_text("Please enter the task summary:")
        return self.SUMMARY

    def _get_epics(self, project_key: str) -> List[Issue]:
        return self.jira_client.search_issues(
            f'project="{project_key}" AND issuetype=Epic AND status in ("To Do", "In Progress")',
        )

    def _get_board_id(self, project_key: str) -> Optional[int]:
        return next(
            (
                board.id
                for board in self.jira_client.boards()
                if project_key in board.name
            ),
            None,
        )

    async def add_summary(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        task_data.summary = update.message.text.strip()

        LOGGER.info("Summary received: %s", task_data.summary)
        await update.message.reply_text(
            'Got it! Now send me the description of the task (or type "skip" to skip).',
        )
        return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        description = update.message.text.strip()
        if description.lower() != "skip":
            task_data.description = description

        components = self.jira_client.project_components(task_data.project_key)
        if components:
            keyboard = [
                [
                    InlineKeyboardButton(component.name, callback_data=component.name)
                    for component in components[i : i + 2]
                ]
                for i in range(0, len(components), 2)
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Got it! Now choose a component from the list below:",
                reply_markup=reply_markup,
            )
            return self.COMPONENT
        else:
            LOGGER.info("No components found for project %s", task_data.project_key)
            await update.message.reply_text(
                "No components found. Proceeding to the next step.",
            )
            return await self.ask_assignee(update, context)

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.component = query.data

        LOGGER.info("Component selected: %s", task_data.component)
        return await self.ask_assignee(query, context)

    async def ask_assignee(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        assignees = self._get_assignees(task_data.project_key)

        if assignees:
            keyboard = [
                [
                    InlineKeyboardButton(assignee, callback_data=assignee)
                    for assignee in assignees[i : i + 2]
                ]
                for i in range(0, len(assignees), 2)
            ]
            keyboard.append([InlineKeyboardButton("Others", callback_data="others")])
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Got it! Now choose an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE
        else:
            LOGGER.info("No assignees found for project %s", task_data.project_key)
            await update.message.reply_text(
                "No assignees found. Proceeding to the next step.",
            )
            return await self.ask_priority(update, context)

    def _get_assignees(self, project_key: str) -> List[str]:
        try:
            assignees = set()
            recent_issues = self.jira_client.search_issues(
                f"project = {project_key} AND createdDate > startOfMonth(-1)",
            )
            for issue in recent_issues:
                if issue.fields.assignee:
                    assignees.add(issue.fields.assignee.name)

            return sorted(assignees) if assignees else []
        except Exception as e:
            LOGGER.error(f"Error fetching assignees for project {project_key}: {e}")
            return []

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
            return await self.ask_priority(query, context)
        else:
            task_data.assignee = query.data
            LOGGER.info("Assignee selected: %s", task_data.assignee)
            return await self.ask_priority(query, context)

    async def search_assignee(self, update: Update, context: CallbackContext) -> int:
        username_query = update.message.text.strip()
        matching_users = self._get_user(username_query)

        if matching_users:
            keyboard = [
                [
                    InlineKeyboardButton(user, callback_data=user)
                    for user in matching_users[i : i + 2]
                ]
                for i in range(0, len(matching_users), 2)
            ]
            keyboard.append([InlineKeyboardButton("Others", callback_data="others")])
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Select an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE_RESULT
        else:
            await update.message.reply_text(
                "No users found. Please enter a different username:",
            )
            return self.ASSIGNEE_SEARCH

    def _get_user(self, username: str) -> List[str]:
        users = self.jira_client.search_users(username, maxResults=50)
        return [user.name for user in users]

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
            return await self.ask_priority(query, context)
        else:
            task_data.assignee = query.data
            LOGGER.info("Assignee selected from search: %s", task_data.assignee)
            return await self.ask_priority(query, context)

    async def ask_priority(self, update: Update, context: CallbackContext) -> int:
        priorities = self.jira_client.priorities()
        keyboard = [
            [
                InlineKeyboardButton(priority.name, callback_data=priority.name)
                for priority in priorities[i : i + 2]
            ]
            for i in range(0, len(priorities), 2)
        ]
        keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Got it! Now choose a priority from the list below:",
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

    async def ask_sprint(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        active_and_future_sprints = [
            sprint
            for sprint in task_data.sprints
            if sprint.state in ("active", "future")
        ]

        if active_and_future_sprints:
            keyboard = [
                [
                    InlineKeyboardButton(sprint.name, callback_data=str(sprint.id))
                    for sprint in active_and_future_sprints[i : i + 2]
                ]
                for i in range(0, len(active_and_future_sprints), 2)
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Got it! Now choose a sprint from the list below:",
                reply_markup=reply_markup,
            )
            return self.SPRINT
        else:
            LOGGER.info("No active or future sprints found.")
            await update.message.reply_text(
                "No active or future sprints found. Proceeding to the next step.",
            )
            return await self.ask_epic(update, context)

    async def add_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.sprint_id = int(query.data)
            LOGGER.info("Sprint selected: %s", task_data.sprint_id)
        else:
            LOGGER.info("Sprint skipped.")

        return await self.ask_epic(query, context)

    async def ask_epic(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        if task_data.epics:
            keyboard = [
                [
                    InlineKeyboardButton(
                        epic.fields.summary,
                        callback_data=epic.key,
                    )
                    for epic in task_data.epics[i : i + 2]
                ]
                for i in range(0, len(task_data.epics), 2)
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Got it! Now choose an epic from the list below:",
                reply_markup=reply_markup,
            )
            return self.EPIC
        else:
            LOGGER.info("No epics found for project %s", task_data.project_key)
            await update.message.reply_text(
                "No epics found. Proceeding to the next step.",
            )
            return await self.ask_release(update, context)

    async def add_epic(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.epic_link = query.data
            LOGGER.info("Epic selected: %s", task_data.epic_link)
        else:
            LOGGER.info("Epic skipped.")

        return await self.ask_release(query, context)

    async def ask_release(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        releases = [
            version
            for version in self.jira_client.project_versions(task_data.project_key)
            if not version.released
        ]

        if releases:
            keyboard = [
                [
                    InlineKeyboardButton(version.name, callback_data=version.name)
                    for version in releases[i : i + 2]
                ]
                for i in range(0, len(releases), 2)
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Got it! Now choose a release from the list below:",
                reply_markup=reply_markup,
            )
            return self.RELEASE
        else:
            LOGGER.info("No unreleased versions found.")
            await update.message.reply_text(
                "No unreleased versions found. Proceeding to the next step.",
            )
            return await self.ask_task_type(update, context)

    async def add_release(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.release = query.data
            LOGGER.info("Release selected: %s", task_data.release)
        else:
            LOGGER.info("Release skipped.")

        return await self.ask_task_type(query, context)

    async def ask_task_type(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        keyboard = [
            [
                InlineKeyboardButton(task_type, callback_data=task_type)
                for task_type in task_data.task_types[i : i + 2]
            ]
            for i in range(0, len(task_data.task_types), 2)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Got it! Now choose a task type from the list below:",
            reply_markup=reply_markup,
        )
        return self.TASK_TYPE

    async def add_task_type(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        task_data.task_type = query.data

        LOGGER.info("Task type selected: %s", task_data.task_type)

        keyboard = [
            [
                InlineKeyboardButton(str(sp), callback_data=str(sp))
                for sp in self.STORY_POINTS_VALUES[i : i + 2]
            ]
            for i in range(0, len(self.STORY_POINTS_VALUES), 2)
        ]
        keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Got it! Now choose the story points:",
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
            """Got it! Now you can send attachments (images, videos, documents).
            When you're done, type 'done' or 'skip' to skip attachments.
            """,
        )
        return self.ATTACHMENT

    async def add_attachment(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        attachments = task_data.attachments
        media_group_messages = context.user_data.setdefault("media_group_messages", {})

        if update.message.text:
            if update.message.text.lower() == "skip":
                LOGGER.info("User chose to skip attachment upload.")
                # Process any collected media groups
                for messages in media_group_messages.values():
                    await self.process_media_group(messages, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return ConversationHandler.END
            elif update.message.text.lower() == "done":
                LOGGER.info("User finished uploading attachments.")
                # Process any collected media groups
                for messages in media_group_messages.values():
                    await self.process_media_group(messages, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "Invalid input. Please type 'done' when finished or 'skip' to skip attachments.",
                )
                return self.ATTACHMENT

        if update.message.media_group_id:
            messages = media_group_messages.setdefault(
                update.message.media_group_id,
                [],
            )
            messages.append(update.message)
            return self.ATTACHMENT  # Stay in ATTACHMENT state to collect more messages

        elif (
            update.message.photo
            or update.message.video
            or update.message.audio
            or update.message.document
        ):
            await self.process_single_media(update.message, attachments)
            await update.message.reply_text(
                "Attachment received. You can send more, or type 'done' to finish.",
            )
            return (
                self.ATTACHMENT
            )  # Stay in ATTACHMENT state to collect more attachments
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

    async def process_single_media(
        self,
        message: Any,
        attachments: Dict[str, List],
    ):
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

    async def finalize_task(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        issue_fields = self.build_issue_fields(task_data)

        try:
            new_issue = self.jira_client.create_issue(fields=issue_fields)
            await self.handle_attachments(new_issue, task_data.attachments)
            await update.message.reply_text(
                f"Task created successfully! Link: {JIRA_SETTINGS.domain}/browse/{new_issue.key}",
            )
        except Exception as e:
            error_message = f"Failed to create task: {e}"
            await update.message.reply_text(error_message)

        return ConversationHandler.END

    def build_issue_fields(self, task_data: TaskData) -> dict:
        issue_fields = {
            "project": {"key": task_data.project_key},
            "summary": task_data.summary,
            "description": task_data.description or "No Description Provided",
            "issuetype": {"name": task_data.task_type or "Task"},
        }

        if task_data.component:
            issue_fields["components"] = [{"name": task_data.component}]
        if task_data.story_points is not None:
            issue_fields[
                "customfield_10106"
            ] = task_data.story_points  # Adjust custom field ID
        if task_data.sprint_id:
            issue_fields[
                "customfield_10104"
            ] = task_data.sprint_id  # Adjust custom field ID
        if task_data.epic_link:
            issue_fields[
                "customfield_10100"
            ] = task_data.epic_link  # Adjust custom field ID
        if task_data.release:
            issue_fields["fixVersions"] = [{"name": task_data.release}]
        if task_data.assignee:
            issue_fields["assignee"] = {"name": task_data.assignee}
        if task_data.priority:
            issue_fields["priority"] = {"name": task_data.priority}

        return issue_fields

    async def handle_attachments(
        self,
        issue: Issue,
        attachments: Dict[str, List],
    ):
        for media_type, files in attachments.items():
            for filename, file_buffer in files:
                self.jira_client.add_attachment(
                    issue=issue,
                    attachment=file_buffer,
                    filename=filename,
                )
        LOGGER.info("Attachments attached to Jira issue")
