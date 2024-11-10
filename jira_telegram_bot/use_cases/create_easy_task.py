from __future__ import annotations

from jira import JIRA
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.use_cases.authentication import check_user_allowed


class JiraEasyTaskCreation:
    PROJECT, SUMMARY, DESCRIPTION, COMPONENT, TASK_TYPE, STORY_POINTS = range(6)

    def __init__(self, jira: JIRA, user_config_instance: UserConfig):
        self.jira = jira
        self.user_config_instance = user_config_instance
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]

    async def start(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        context.user_data.clear()

        user = update.message.from_user.username
        config = self.user_config_instance.get_user_config(user)

        if config:
            context.user_data["config"] = config
            context.user_data["project_key"] = config.get("project")
            context.user_data["component"] = config.get("component")
            context.user_data["task_type"] = config.get("task_type")
        else:
            context.user_data["config"] = {}

        # Prompt user for project if not specified in config
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
        return await self.ask_for_summary(query, context)

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

        component = context.user_data["config"].get("component")
        if isinstance(component, list) and len(component) > 1:
            keyboard = [
                [InlineKeyboardButton(comp, callback_data=comp)] for comp in component
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            await update.message.reply_text(
                "Select a component:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return self.COMPONENT
        elif component:
            context.user_data["component"] = (
                component[0] if isinstance(component, list) else component
            )
            return await self.ask_for_task_type(update, context)
        else:
            return await self.ask_for_task_type(update, context)

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["component"] = query.data
        return await self.ask_for_task_type(query, context)

    async def ask_for_task_type(self, update: Update, context: CallbackContext) -> int:
        task_type = context.user_data["config"].get("task_type")
        if isinstance(task_type, list) and len(task_type) > 1:
            keyboard = [[InlineKeyboardButton(t, callback_data=t)] for t in task_type]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            await update.message.reply_text(
                "Select a task type:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return self.TASK_TYPE
        elif task_type:
            context.user_data["task_type"] = (
                task_type[0] if isinstance(task_type, list) else task_type
            )
            return await self.ask_for_story_points(update, context)
        else:
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
        if update.message:
            await update.message.reply_text(
                "Select story points:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await update.callback_query.message.edit_text(
                "Select story points:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return self.STORY_POINTS

    async def add_story_points(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["story_points"] = float(query.data)
        await self.finalize_task(update, context)
        return ConversationHandler.END

    async def finalize_task(self, update: Update, context: CallbackContext) -> int:
        config = context.user_data.get("config", {})
        project_key = context.user_data["project_key"]
        summary = context.user_data["summary"]
        description = context.user_data.get("description", "No Description Provided")
        component = context.user_data.get("component", config.get("component"))
        task_type = context.user_data.get("task_type", config.get("task_type"))
        story_points = context.user_data.get("story_points")

        issue_fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": task_type or "Task"},
        }

        if component:
            issue_fields["components"] = [{"name": component}]
        if story_points is not None:
            issue_fields["customfield_10106"] = story_points

        try:
            new_issue = self.jira.create_issue(fields=issue_fields)
            if update.message:
                await update.message.reply_text(
                    f"Task created successfully! Link: {new_issue.permalink()}",
                )
            else:
                await update.callback_query.message.edit_text(
                    f"Task created successfully! Link: {new_issue.permalink()}",
                )
        except Exception as e:
            error_message = f"Failed to create task: {e}"
            if update.message:
                await update.message.reply_text(error_message)
            else:
                await update.callback_query.message.edit_text(error_message)

        return ConversationHandler.END
