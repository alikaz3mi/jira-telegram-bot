from __future__ import annotations

from jira import JIRA
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.use_cases.authentication import check_user_allowed


class JiraEasyTaskCreation:
    (
        PROJECT,
        SUMMARY,
        DESCRIPTION,
        COMPONENT,
        BOARD_NAME,
        TASK_TYPE,
        STORY_POINTS,
    ) = range(7)

    def __init__(self, jira: JIRA, user_config_instance: UserConfig):
        self.jira = jira
        self.user_config_instance = user_config_instance
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]  # Example values

    async def start(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        user = update.message.from_user.username
        config = self.user_config_instance.get_user_config(user)

        if config:
            context.user_data["config"] = config
            # Set defaults from config if available
            context.user_data["project_key"] = config.get("project")
            context.user_data["component"] = config.get("component")
            context.user_data["task_type"] = config.get("task_type")

        # If the project is not specified, prompt the user to select one
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
        return await self.ask_for_summary(update, context)

    async def ask_for_summary(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text("Please enter the task summary:")
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

        # Check if component is predefined
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
            return await self.ask_for_board_name(update, context)
        else:
            return await self.ask_for_board_name(update, context)

    async def add_component(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        if query.data != "skip":
            context.user_data["component"] = query.data
        return await self.ask_for_board_name(query, context)

    async def ask_for_board_name(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text(
            "Enter the board name (or type 'skip' to skip):",
        )
        return self.BOARD_NAME

    async def add_board_name(self, update: Update, context: CallbackContext) -> int:
        board_name = update.message.text.strip()
        if board_name.lower() != "skip":
            context.user_data["board_name"] = board_name

        # Check if task type is predefined
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
            [InlineKeyboardButton(str(sp), callback_data=str(sp))]
            for sp in self.STORY_POINTS_VALUES
        ]
        keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
        await update.message.reply_text(
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
            "issuetype": {
                "name": task_type or "Task",
            },  # Default to 'Task' if not specified
        }

        if component:
            issue_fields["components"] = [{"name": component}]
        if story_points is not None:
            issue_fields[
                "customfield_story_points"
            ] = story_points  # Replace with actual field ID if needed

        try:
            new_issue = self.jira.create_issue(fields=issue_fields)
            await update.message.reply_text(
                f"Task created successfully! Link: {new_issue.permalink()}",
            )
        except Exception as e:
            await update.message.reply_text(f"Failed to create task: {e}")

        return ConversationHandler.END
