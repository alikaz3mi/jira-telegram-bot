from __future__ import annotations

from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import aiohttp
from jira import Issue
from PIL import Image
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.authentication import check_user_allowed
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraEasyTaskCreation:
    (
        PROJECT,
        SUMMARY,
        DESCRIPTION,
        COMPONENT,
        TASK_TYPE,
        STORY_POINTS,
        SPRINT,
        ATTACHMENT,
        EPIC_LINK,
        RELEASE,
    ) = range(10)

    def __init__(
        self,
        jira_client: TaskManagerRepositoryInterface,
        user_config_instance: UserConfig,
        logger=LOGGER,
    ):
        self.jira_client = jira_client
        self.user_config_instance = user_config_instance
        self.logger = logger
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]
        self.media_group_timeout = 1.0

    async def start(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        context.user_data.clear()
        user = update.message.from_user.username
        user_config = self.user_config_instance.get_user_config(user)

        task_data = TaskData()
        context.user_data["task_data"] = task_data

        if user_config:
            task_data.config = user_config.dict()
            task_data.project_key = (
                user_config.project.values[0]
                if len(user_config.project.values) == 1
                else None
            )

        if not task_data.project_key:
            return await self.ask_for_project(update, context)
        else:
            return await self.ask_for_summary(update, context)

    async def ask_for_project(self, update: Update, context: CallbackContext) -> int:
        projects = self.jira_client.get_projects()
        keyboard = self.build_keyboard(
            [project.name for project in projects],
            data=[project.key for project in projects],
        )
        await self.send_message(
            update,
            "Please select a project:",
            reply_markup=keyboard,
        )
        return self.PROJECT

    async def add_project(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        task_data.project_key = query.data
        self._get_additional_info_of_the_board(task_data)
        return await self.ask_for_summary(query, context)

    def _get_additional_info_of_the_board(self, task_data: TaskData):
        if task_data.config.get("epic_link", {}).get("set_field", False):
            task_data.epics = self.jira_client.get_epics(task_data.project_key)
        task_data.board_id = self._get_board_id(task_data.project_key)

    def _get_board_id(self, project_key: str):
        boards = self.jira_client.get_boards()
        return next(
            (board.id for board in boards if project_key in board.name),
            None,
        )

    async def ask_for_summary(self, update: Update, context: CallbackContext) -> int:
        await self.send_message(update, "Please enter the task summary:")
        return self.SUMMARY

    async def add_summary(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        task_data.summary = update.message.text.strip()
        await update.message.reply_text(
            "Please enter the task description (or type 'skip' to skip):",
        )
        return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        description = update.message.text.strip()
        if description.lower() != "skip":
            task_data.description = description
        return await self.handle_component_selection(update, context)

    async def handle_component_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        task_data = context.user_data["task_data"]
        component_config = task_data.config.get("component")
        if component_config and component_config.get("set_field"):
            if component_config["values"]:
                if len(component_config["values"]) > 1:
                    keyboard = self.build_keyboard(
                        component_config["values"],
                        include_skip=True,
                    )
                    await update.message.reply_text(
                        "Select a component:",
                        reply_markup=keyboard,
                    )
                    return self.COMPONENT
                task_data.component = component_config["values"][0]
            else:
                components = self.jira_client.get_project_components(
                    task_data.project_key,
                )
                if components:
                    component_names = [component.name for component in components]
                    keyboard = self.build_keyboard(component_names, include_skip=True)
                    await update.message.reply_text(
                        "Select a component:",
                        reply_markup=keyboard,
                    )
                    return self.COMPONENT
        return await self.ask_for_task_type(update, context)

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        if query.data != "skip":
            task_data.component = query.data
        return await self.ask_for_task_type(query, context)

    async def ask_for_task_type(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        task_type_config = task_data.config.get("task_type")
        if task_type_config and task_type_config["set_field"]:
            if task_type_config["values"]:
                keyboard = self.build_keyboard(
                    task_type_config["values"],
                    include_skip=True,
                )
                await self.send_message(
                    update,
                    "Select a task type:",
                    reply_markup=keyboard,
                )
                return self.TASK_TYPE
            else:
                task_data.task_types = [
                    z.name
                    for z in self.jira_client.issue_types_for_project(
                        task_data.project_key,
                    )
                ]

        task_data.task_type = (
            task_type_config["values"][0]
            if task_type_config and task_type_config["values"]
            else "Task"
        )
        return await self.ask_for_story_points(update, context)

    async def add_task_type(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        if query.data != "skip":
            task_data.task_type = query.data
        return await self.ask_for_story_points(query, context)

    async def ask_for_story_points(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        keyboard = self.build_keyboard(
            [str(sp) for sp in self.STORY_POINTS_VALUES],
            include_skip=True,
            row_width=3,
        )
        await self.send_message(update, "Select story points:", reply_markup=keyboard)
        return self.STORY_POINTS

    async def add_story_points(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        if query.data != "skip":
            task_data.story_points = float(query.data)

        sprint_config = task_data.config.get("sprint")
        if sprint_config and sprint_config["set_field"]:
            return await self.ask_for_sprint(update, context)
        return await self.ask_for_epic_link(update, context)

    async def ask_for_sprint(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        if task_data.board_id:
            sprints = self.jira_client.get_sprints(task_data.board_id)
            unstarted_sprints = [
                sprint
                for sprint in sprints
                if sprint.state in ("future", "backlog", "active")
            ]
            if unstarted_sprints:
                sprint_names = [sprint.name for sprint in unstarted_sprints]
                sprint_ids = [str(sprint.id) for sprint in unstarted_sprints]
                keyboard = self.build_keyboard(
                    sprint_names,
                    data=sprint_ids,
                    include_skip=True,
                )
                await self.send_message(
                    update,
                    "Choose a sprint from the list below:",
                    reply_markup=keyboard,
                )
                return self.SPRINT
        await self.send_message(
            update,
            "No available sprints found. Proceeding without sprint selection.",
        )
        return await self.ask_for_epic_link(update, context)

    async def add_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        if query.data != "skip":
            task_data.sprint_id = int(query.data)
        return await self.ask_for_epic_link(query, context)

    async def ask_for_epic_link(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        epic_config = task_data.config.get("epic_link")
        if epic_config and epic_config["set_field"] and task_data.epics:
            epic_keys = [epic.key for epic in task_data.epics]
            keyboard = self.build_keyboard(epic_keys, include_skip=True)
            await self.send_message(
                update,
                "Select an Epic Link:",
                reply_markup=keyboard,
            )
            return self.EPIC_LINK
        return await self.ask_for_release(update, context)

    async def add_epic_link(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        if query.data != "skip":
            task_data.epic_link = query.data
        return await self.ask_for_release(query, context)

    async def ask_for_release(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        release_config = task_data.config.get("release")
        if release_config and release_config["set_field"]:
            releases = [
                release
                for release in self.jira_client.get_project_versions(
                    task_data.project_key,
                )
                if not release.released
            ]
            if releases:
                release_names = [release.name for release in releases]
                keyboard = self.build_keyboard(release_names, include_skip=True)
                await self.send_message(
                    update,
                    "Select a Release:",
                    reply_markup=keyboard,
                )
                return self.RELEASE
            else:
                await self.send_message(
                    update,
                    "No available Releases found. Proceeding without release selection.",
                )
        return await self.ask_for_attachment(update, context)

    async def add_release(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        task_data = context.user_data["task_data"]
        if query.data != "skip":
            task_data.release = query.data
        return await self.ask_for_attachment(query, context)

    async def ask_for_attachment(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text(
            """
            Please upload any attachments. When you are done, type 'done'.
            If you wish to skip attachments, type 'skip'.
            """,
        )
        return self.ATTACHMENT

    async def add_attachment(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        attachments = task_data.attachments
        media_group_messages = context.user_data.setdefault("media_group_messages", {})

        if update.message.text:
            if update.message.text.lower() == "skip":
                self.logger.info("User chose to skip attachment upload.")
                for messages in media_group_messages.values():
                    await self.process_media_group(messages, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return ConversationHandler.END
            elif update.message.text.lower() == "done":
                self.logger.info("User finished uploading attachments.")
                for messages in media_group_messages.values():
                    await self.process_media_group(messages, attachments)
                media_group_messages.clear()
                await self.finalize_task(update, context)
                return ConversationHandler.END

        if update.message.media_group_id:
            LOGGER.info(f"media = {update.message.media_group_id}")
            messages = media_group_messages.setdefault(
                update.message.media_group_id,
                [],
            )
            messages.append(update.message)
            return self.ATTACHMENT

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
            return self.ATTACHMENT
        else:
            await update.message.reply_text(
                "Please upload an attachment or type 'done' when finished.",
            )
            return self.ATTACHMENT

    async def finalize_task(self, update: Update, context: CallbackContext) -> int:
        task_data = context.user_data["task_data"]
        issue_fields = self.build_issue_fields(task_data)

        try:
            new_issue = self.jira_client.create_issue(fields=issue_fields)
            await self.handle_attachments(new_issue, task_data.attachments)
            await self.send_message(
                update,
                f"Task created successfully! Link: {new_issue.permalink()}",
            )
        except Exception as e:
            error_message = f"Failed to create task: {e}"
            await self.send_message(update, error_message)

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
            issue_fields["customfield_10106"] = task_data.story_points
        if task_data.sprint_id:
            issue_fields["customfield_10104"] = task_data.sprint_id
        if task_data.epic_link:
            issue_fields["customfield_10105"] = task_data.epic_link
        if task_data.release:
            issue_fields["fixVersions"] = [{"name": task_data.release}]

        return issue_fields

    async def process_media_group(
        self,
        messages: List[Any],
        attachments: Dict[str, List[BytesIO]],
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

    async def process_single_media(
        self,
        message: Any,
        attachments: Dict[str, List[BytesIO]],
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

    async def fetch_and_store_media(self, media, session, storage_list, filename):
        media_file = await media.get_file()
        async with session.get(media_file.file_path) as response:
            if response.status == 200:
                buffer = BytesIO(await response.read())
                storage_list.append(buffer)
                if "image" in filename:
                    image = Image.open(buffer)
                    image.save(filename, format="JPEG")
            else:
                self.logger.error(f"Failed to fetch media from {media_file.file_path}")

    async def handle_attachments(
        self,
        issue: Issue,
        attachments: Dict[str, List[BytesIO]],
    ):
        LOGGER.info(f"Attachments = {attachments}")
        for media_type, files in attachments.items():
            for idx, file_buffer in enumerate(files):
                filename = f"{media_type}_{idx}.{self.get_file_extension(media_type)}"
                self.jira_client.add_attachment(
                    issue=issue,
                    attachment=file_buffer,
                    filename=filename,
                )
        self.logger.info("Attachments attached to Jira issue")

    def get_file_extension(self, media_type: str) -> str:
        return {
            "images": "jpg",
            "videos": "mp4",
            "audio": "mp3",
            "documents": "txt",
        }.get(media_type, "bin")

    def build_keyboard(
        self,
        options: List[str],
        data: Optional[List[str]] = None,
        include_skip: bool = False,
        row_width: int = 2,
    ) -> InlineKeyboardMarkup:
        if not data:
            data = options
        keyboard = [
            [
                InlineKeyboardButton(text=option, callback_data=data[i + j])
                for j, option in enumerate(options[i : i + row_width])
            ]
            for i in range(0, len(options), row_width)
        ]
        if include_skip:
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        return InlineKeyboardMarkup(keyboard)

    async def send_message(self, update: Update, text: str, reply_markup=None):
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.message.edit_text(
                text,
                reply_markup=reply_markup,
            )
        else:
            LOGGER.error("other type of message in send message is not handled")
            raise Exception("other type of message in send message is not handled")
