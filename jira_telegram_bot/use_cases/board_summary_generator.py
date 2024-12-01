from __future__ import annotations

from typing import List
from typing import Optional

from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.authentication import check_user_allowed
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class BoardSummaryGenerator:
    (
        PROJECT,
        COMPONENT,
        ASSIGNEE,
        SPRINT,
        EPIC,
        RELEASE,
        ASSIGNEE_SEARCH,
        ASSIGNEE_RESULT,
    ) = range(8)

    def __init__(self, jira_repository: TaskManagerRepositoryInterface):
        self.jira_repository = jira_repository

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
        keyboard = [
            [
                InlineKeyboardButton(text=option, callback_data=data[i + j])
                for j, option in enumerate(options[i : i + row_width])
            ]
            for i in range(0, len(options), row_width)
        ]
        if extra_buttons:
            keyboard.extend(extra_buttons)
        if include_skip:
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        context.user_data.clear()
        task_data = TaskData()
        context.user_data["task_data"] = task_data

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

        return await self.ask_component(query, context)

    async def ask_component(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        components = self.jira_repository.get_project_components(task_data.project_key)
        if components:
            options = [component.name for component in components]
            data = [component.name for component in components]
            reply_markup = self.build_keyboard(options, data, include_skip=True)
            await update.message.reply_text(
                "Please select a component from the list below:",
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
        else:
            LOGGER.info("Component skipped.")
            task_data.component = None

        return await self.ask_assignee(query, context)

    async def ask_assignee(self, update: Update, context: CallbackContext) -> int:
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
            await update.message.reply_text(
                "Now choose an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE
        else:
            LOGGER.info("No assignees found for project %s", task_data.project_key)
            await update.message.reply_text(
                "No assignees found. Proceeding to the next step.",
            )
            return await self.ask_sprint(update, context)

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
            return await self.ask_sprint(query, context)
        else:
            task_data.assignee = query.data
            LOGGER.info("Assignee selected: %s", task_data.assignee)
            return await self.ask_sprint(query, context)

    async def search_assignee(self, update: Update, context: CallbackContext) -> int:
        username_query = update.message.text.strip()
        matching_users = self.jira_repository.search_users(username_query)

        if matching_users:
            options = matching_users
            data = matching_users
            extra_buttons = [[InlineKeyboardButton("Others", callback_data="others")]]
            reply_markup = self.build_keyboard(
                options,
                data,
                row_width=2,
                include_skip=True,
                extra_buttons=extra_buttons,
            )
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
            return await self.ask_sprint(query, context)
        else:
            task_data.assignee = query.data
            LOGGER.info("Assignee selected from search: %s", task_data.assignee)
            return await self.ask_sprint(query, context)

    async def ask_sprint(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        active_and_future_sprints = [
            sprint
            for sprint in task_data.sprints
            if sprint.state in ("active", "future")
        ]

        if active_and_future_sprints:
            options = [sprint.name for sprint in active_and_future_sprints]
            data = [str(sprint.id) for sprint in active_and_future_sprints]
            reply_markup = self.build_keyboard(
                options,
                data,
                include_skip=True,
            )
            await update.message.reply_text(
                "Now choose a sprint from the list below:",
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
            task_data.sprint_id = None

        return await self.ask_epic(query, context)

    async def ask_epic(self, update: Update, context: CallbackContext) -> int:
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
            await update.message.reply_text(
                "Now choose an epic from the list below:",
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
            task_data.epic_link = None

        return await self.ask_release(query, context)

    async def ask_release(self, update: Update, context: CallbackContext) -> int:
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
            reply_markup = self.build_keyboard(
                options,
                include_skip=True,
                row_width=3,
            )
            await update.message.reply_text(
                "Now choose a release from the list below:",
                reply_markup=reply_markup,
            )
            return self.RELEASE
        else:
            LOGGER.info("No unreleased versions found.")
            await update.message.reply_text(
                "No unreleased versions found. Proceeding to fetch tasks.",
            )
            return await self.fetch_tasks(update, context)

    async def add_release(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()

        task_data: TaskData = context.user_data["task_data"]
        if query.data != "skip":
            task_data.release = query.data
            LOGGER.info("Release selected: %s", task_data.release)
        else:
            LOGGER.info("Release skipped.")
            task_data.release = None

        return await self.fetch_tasks(query, context)

    async def fetch_tasks(self, update: Update, context: CallbackContext) -> int:
        task_data: TaskData = context.user_data["task_data"]
        jql_parts = [f'project = "{task_data.project_key}"']
        jql_parts.append("status  in (Review, Done)")

        if task_data.component:
            jql_parts.append(f'component = "{task_data.component}"')
        if task_data.assignee:
            jql_parts.append(f'assignee = "{task_data.assignee}"')
        if task_data.sprint_id:
            jql_parts.append(f"sprint = {task_data.sprint_id}")
        if task_data.epic_link:
            jql_parts.append(f'"Epic Link" = "{task_data.epic_link}"')
        if task_data.release:
            jql_parts.append(f'fixVersion = "{task_data.release}"')

        jql_query = " AND ".join(jql_parts)
        LOGGER.info(f"Fetching tasks with JQL: {jql_query}")

        try:
            issues = self.jira_repository.jira.search_issues(jql_query)
            if issues:
                response_text = "Found the following tasks:\n"
                for issue in issues:
                    response_text += f"- {issue.key}: {issue.fields.summary}\n"
                await update.message.reply_text(response_text)
            else:
                await update.message.reply_text("No tasks found matching the criteria.")
        except Exception as e:
            error_message = f"Failed to fetch tasks: {e}"
            await update.message.reply_text(error_message)

        return ConversationHandler.END
