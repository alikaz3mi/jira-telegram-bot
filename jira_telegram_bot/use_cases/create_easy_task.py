from __future__ import annotations

import asyncio
from collections import defaultdict
from io import BytesIO

import aiohttp
from jira import JIRA
from PIL import Image
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.use_cases.authentication import check_user_allowed


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

    def __init__(self, jira: JIRA, user_config_instance: UserConfig):
        self.jira = jira
        self.user_config_instance = user_config_instance
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]
        self.EPICS = None
        self.media_group_timeout = 1.0

    async def start(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        context.user_data.clear()
        user = update.message.from_user.username
        user_config = self.user_config_instance.get_user_config(user)

        if user_config:
            context.user_data["config"] = user_config.dict()
            context.user_data["project_key"] = (
                user_config.project.values[0] if user_config.project.values else None
            )
        else:
            context.user_data["config"] = {}

        if not context.user_data.get("project_key"):
            return await self.ask_for_project(update, context)
        else:
            return await self.ask_for_summary(update, context)

    async def ask_for_project(self, update: Update, context: CallbackContext) -> int:
        projects = self.jira.projects()
        keyboard = [
            [
                InlineKeyboardButton(project.name, callback_data=project.key)
                for project in projects[i : i + 2]
            ]
            for i in range(0, len(projects), 2)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Please select a project:",
            reply_markup=reply_markup,
        )
        return self.PROJECT

    async def add_project(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["project_key"] = query.data
        self.JIRA_PROJECT_KEY = context.user_data["project_key"]
        self._get_additional_info_of_the_board(context)
        return await self.ask_for_summary(query, context)

    def _get_additional_info_of_the_board(self, context):
        if context.user_data["config"].get("epic_link", {}).get("set_field", False):
            self.EPICS = self._get_epics(self.JIRA_PROJECT_KEY)
        self.BOARD_ID = self._get_board_id(self.JIRA_PROJECT_KEY)

    def _get_epics(self, project_key: str):
        return [
            epic
            for epic in self.jira.search_issues(
                f'project={project_key} AND issuetype=Epic AND status in ("To Do", "In Progress")',
            )
        ]

    def _get_board_id(self, project_key: str):
        return next(
            (board.id for board in self.jira.boards() if project_key in board.name),
            None,
        )

    async def ask_for_summary(self, update: Update, context: CallbackContext) -> int:
        if update.message:
            await update.message.reply_text("Please enter the task summary:")
        else:
            await update.callback_query.message.edit_text(
                "Please enter the task summary:",
            )
        return self.SUMMARY

    async def add_summary(self, update: Update, context: CallbackContext) -> int:
        summary = update.message.text.strip()
        context.user_data["summary"] = summary
        await update.message.reply_text(
            "Please enter the task description (or type 'skip' to skip):",
        )
        return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        description = update.message.text.strip()
        if description.lower() != "skip":
            context.user_data["description"] = description

        component_config = context.user_data["config"].get("component")
        if component_config and component_config.get("set_field"):
            if component_config["values"]:
                if len(component_config["values"]) > 1:
                    keyboard = [
                        [InlineKeyboardButton(comp, callback_data=comp)]
                        for comp in component_config["values"]
                    ]
                    keyboard.append(
                        [InlineKeyboardButton("Skip", callback_data="skip")],
                    )
                    await update.message.reply_text(
                        "Select a component:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )
                    return self.COMPONENT
                context.user_data["component"] = component_config["values"][0]
            else:
                components = self.jira.project_components(self.JIRA_PROJECT_KEY)
                if components:
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                component.name,
                                callback_data=component.name,
                            )
                            for component in components[i : i + 2]
                        ]
                        for i in range(0, len(components), 2)
                    ]
                    keyboard.append(
                        [InlineKeyboardButton("Skip", callback_data="skip")],
                    )
                    await update.message.reply_text(
                        "Select a component:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )
                    return self.COMPONENT

        return await self.ask_for_task_type(update, context)

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["component"] = query.data
        return await self.ask_for_task_type(query, context)

    async def ask_for_task_type(self, update: Update, context: CallbackContext) -> int:
        task_type = context.user_data["config"].get("task_type")
        if task_type and task_type["set_field"]:
            if task_type["values"]:
                keyboard = [
                    [InlineKeyboardButton(t, callback_data=t)]
                    for t in task_type["values"]
                ]
                keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
                await update.message.reply_text(
                    "Select a task type:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
                return self.TASK_TYPE
        context.user_data["task_type"] = (
            task_type["values"][0] if task_type and task_type["values"] else "Task"
        )
        return await self.ask_for_story_points(update, context)

    async def add_task_type(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["task_type"] = query.data
        return await self.ask_for_story_points(query, context)

    async def ask_for_story_points(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        keyboard = [
            [
                InlineKeyboardButton(str(sp), callback_data=str(sp))
                for sp in self.STORY_POINTS_VALUES[i : i + 3]
            ]
            for i in range(0, len(self.STORY_POINTS_VALUES), 3)
        ]
        keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(
                "Select story points:",
                reply_markup=reply_markup,
            )
        elif update.callback_query:
            await update.callback_query.message.edit_text(
                "Select story points:",
                reply_markup=reply_markup,
            )

        return self.STORY_POINTS

    async def add_story_points(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["story_points"] = float(query.data)

        sprint_config = context.user_data["config"].get("sprint")
        if sprint_config and sprint_config["set_field"]:
            return await self.ask_for_sprint(update, context)

        return await self.ask_for_epic_link(update, context)

    async def ask_for_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query

        if self.BOARD_ID:
            sprints = self.jira.sprints(board_id=self.BOARD_ID)
            unstarted_sprints = [
                sprint
                for sprint in sprints
                if sprint.state in ("future", "backlog", "active")
            ]

            keyboard = [
                [InlineKeyboardButton(sprint.name, callback_data=sprint.id)]
                for sprint in unstarted_sprints
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Got it! Now choose a sprint from the list below:",
                reply_markup=reply_markup,
            )
            return self.SPRINT

        await update.message.reply_text(
            "No available sprints found. Proceeding without sprint selection.",
        )
        return await self.ask_for_epic_link(update, context)

    async def add_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["sprint_id"] = query.data
        return await self.ask_for_epic_link(query, context)

    async def ask_for_epic_link(self, update: Update, context: CallbackContext) -> int:
        epic_config = context.user_data["config"].get("epic_link")
        if epic_config and epic_config["set_field"] and self.EPICS:
            keyboard = [
                [InlineKeyboardButton(epic.key, callback_data=epic.key)]
                for epic in self.EPICS
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Select an Epic Link:",
                reply_markup=reply_markup,
            )
            return self.EPIC_LINK
        else:
            return await self.ask_for_release(update, context)

    async def add_epic_link(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["epic_link"] = query.data
        return await self.ask_for_release(query, context)

    async def ask_for_release(self, update: Update, context: CallbackContext) -> int:
        release_config = context.user_data["config"].get("release")
        if release_config and release_config["set_field"]:
            releases = [
                release
                for release in self.jira.project_versions(self.JIRA_PROJECT_KEY)
                if not release.released
            ]
            if releases:
                keyboard = [
                    [InlineKeyboardButton(release.name, callback_data=release.name)]
                    for release in releases
                ]
                keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Select a Release:",
                    reply_markup=reply_markup,
                )
                return self.RELEASE
            else:
                await update.message.reply_text(
                    "No available Releases found. Proceeding without release selection.",
                )
        return await self.ask_for_attachment(update, context)

    async def add_release(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["release"] = query.data
        return await self.ask_for_attachment(query, context)

    async def ask_for_attachment(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text(
            "Please upload an attachment or type 'skip' to continue.",
        )
        return self.ATTACHMENT

    async def add_attachment(self, update: Update, context: CallbackContext) -> int:
        # Initialize or retrieve the user's attachment storage and media group
        attachments = context.user_data.setdefault(
            "attachments",
            {"images": [], "videos": [], "audio": [], "documents": []},
        )
        media_group_messages = context.user_data.setdefault(
            "media_group_messages",
            defaultdict(list),
        )

        # Handle skip command
        if update.message.text and update.message.text.lower() == "skip":
            LOGGER.info("User chose to skip image upload.")
            await self.finalize_task(update, context)
            return ConversationHandler.END

        # Handle media group
        if update.message.media_group_id:
            # Add the message to the user's specific media group collection
            media_group_messages[update.message.media_group_id].append(update.message)

            # Wait for more media in the group, with a timeout
            await asyncio.sleep(self.media_group_timeout)

            # Check if we have finished receiving media for the group
            if len(set(media_group_messages[update.message.media_group_id])) == len(
                media_group_messages[update.message.media_group_id],
            ):
                async with aiohttp.ClientSession() as session:
                    for idx, media_message in enumerate(
                        media_group_messages[update.message.media_group_id],
                    ):
                        photo = media_message.photo[-1]  # Highest resolution
                        media_file = await photo.get_file()
                        async with session.get(media_file.file_path) as response:
                            if response.status == 200:
                                buffer = BytesIO(await response.read())
                                attachments["images"].append(buffer)
                                image = Image.open(buffer)
                                image.save(f"image_{idx}.jpg", format="JPEG")
                            else:
                                LOGGER.error(
                                    f"Failed to fetch media from {media_file.file_path}",
                                )
                # Update user data with attachments and clear media group
                context.user_data["attachments"] = attachments
                del media_group_messages[update.message.media_group_id]

                await update.message.reply_text(
                    "All images in the album have been received.",
                )
                return await self.finalize_task(
                    update,
                    context,
                )  # Finalize after collection

            # Continue in the same stage to collect remaining items
            return self.ATTACHMENT

        # Handle single media files (non-media group)
        elif update.message.photo or update.message.video or update.message.audio:
            async with aiohttp.ClientSession() as session:
                if update.message.photo:
                    photo = sorted(
                        update.message.photo,
                        key=lambda x: x.file_size,
                        reverse=True,
                    )[0]
                    photo_file = await photo.get_file()
                    async with session.get(photo_file.file_path) as response:
                        if response.status == 200:
                            buffer = BytesIO(await response.read())
                            attachments["images"].append(buffer)
                            image = Image.open(buffer)
                            image.save("single_image.jpg", format="JPEG")
                elif update.message.video:
                    video_file = await update.message.video.get_file()
                    async with session.get(video_file.file_path) as response:
                        if response.status == 200:
                            buffer = BytesIO(await response.read())
                            attachments["videos"].append(buffer)
                elif update.message.audio:
                    audio_file = await update.message.audio.get_file()
                    async with session.get(audio_file.file_path) as response:
                        if response.status == 200:
                            buffer = BytesIO(await response.read())
                            attachments["audio"].append(buffer)

            context.user_data["attachments"] = attachments
            await update.message.reply_text("Single media file has been received.")
            return await self.finalize_task(
                update,
                context,
            )  # Finalize for single media

    async def finalize_task(self, update: Update, context: CallbackContext) -> int:
        config = context.user_data.get("config", {})
        project_key = context.user_data["project_key"]
        summary = context.user_data["summary"]
        description = context.user_data.get("description", "No Description Provided")
        component = context.user_data.get("component", config.get("component"))
        task_type = context.user_data.get("task_type", config.get("task_type"))
        story_points = context.user_data.get("story_points")
        sprint_id = context.user_data.get("sprint_id")
        epic_link = context.user_data.get("epic_link")
        release = context.user_data.get("release")
        attachment = context.user_data.get("attachments")

        issue_fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": task_type or "Task"},
        }

        if component:
            issue_fields["components"] = [{"name": component}]
        if story_points is not None:
            issue_fields[
                "customfield_10106"
            ] = story_points  # Replace with actual field ID for story points
        if sprint_id:
            issue_fields["customfield_10104"] = int(
                sprint_id,
            )  # Replace with actual field ID for sprint
        if epic_link:
            issue_fields[
                "customfield_10105"
            ] = epic_link  # Replace with actual field ID for epic link
        if release:
            issue_fields["fixVersions"] = [{"name": release}]

        try:
            new_issue = self.jira.create_issue(fields=issue_fields)
            if attachment:
                for key, values in attachment.items():
                    data_type = {
                        "images": "jpg",
                        "videos": "mp4",
                        "audio": "mp3",
                        "documents": "txt",
                    }[key]
                    for idx, value in enumerate(values):
                        self.jira.add_attachment(
                            issue=new_issue,
                            attachment=value,
                            filename=f"{idx}.{data_type}",
                        )
                LOGGER.info("Attachments attached to Jira issue")

            if update.message:
                await update.message.reply_text(
                    f"Task created successfully! Link: {new_issue.permalink()}",
                )
            elif update.callback_query:
                await update.callback_query.message.edit_text(
                    f"Task created successfully! Link: {new_issue.permalink()}",
                )
        except Exception as e:
            error_message = f"Failed to create task: {e}"
            if update.message:
                await update.message.reply_text(error_message)
            elif update.callback_query:
                await update.callback_query.message.edit_text(error_message)

        return ConversationHandler.END
