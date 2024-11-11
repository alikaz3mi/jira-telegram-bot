from __future__ import annotations

from jira import JIRA
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler
from telegram.ext import filters

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
        if context.user_data["config"].get("epic_link")["set_field"]:
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
        if self.EPICS:
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
            await update.message.reply_text(
                "No available Epics found. Proceeding without epic link selection.",
            )
            return await self.ask_for_release(update, context)

    async def add_epic_link(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["epic_link"] = query.data
        return await self.ask_for_release(query, context)

    async def ask_for_release(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text(
            "Please specify the release (or type 'skip' to skip):",
        )
        return self.RELEASE

    async def add_release(self, update: Update, context: CallbackContext) -> int:
        release = update.message.text.strip()
        if release.lower() != "skip":
            context.user_data["release"] = release
        return await self.ask_for_attachment(update, context)

    async def ask_for_attachment(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text(
            "Please upload an attachment or type 'skip' to continue.",
        )
        return self.ATTACHMENT

    async def add_attachment(self, update: Update, context: CallbackContext) -> int:
        if update.message and update.message.document:
            document = update.message.document
            context.user_data["attachment"] = document.file_id
        elif update.message and update.message.photo:
            context.user_data["attachment"] = update.message.photo[-1].file_id
        return await self.finalize_task(update, context)

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
        attachment = context.user_data.get("attachment")

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
                file = await update.message.bot.get_file(attachment)
                file_path = await file.download_as_bytearray()
                self.jira.add_attachment(issue=new_issue, attachment=file_path)

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
