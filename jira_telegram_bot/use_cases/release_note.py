from __future__ import annotations

from jira import JIRA
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_BOARD_SETTINGS


class JiraTaskTransition:
    START = range(1)

    def __init__(self, jira: JIRA):
        self.jira = jira

    def build_inline_keyboard(self, items, row_size=2):
        """Helper function to build an inline keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(item, callback_data=item)
                for item in items[i : i + row_size]
            ]
            for i in range(0, len(items), row_size)
        ]
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
        return InlineKeyboardMarkup(keyboard)

    async def start_transition(self, update: Update, context: CallbackContext) -> int:
        """Start the task transition process by selecting the assignee."""
        keyboard = self.build_inline_keyboard(self.assignees, row_size=2)
        await update.message.reply_text(
            "Please choose who you are:",
            reply_markup=keyboard,
        )
        LOGGER.info("User started the task transition process")
        return self.ASSIGNEE

    async def select_assignee(self, update: Update, context: CallbackContext) -> int:
        """Handle the selection of an assignee and show their tasks."""
        query = update.callback_query
        await query.answer()

        assignee = query.data
        if assignee == "cancel":
            await query.edit_message_text("Task transition process cancelled.")
            return ConversationHandler.END

        context.user_data["assignee"] = assignee
        LOGGER.info("Assignee selected: %s", assignee)

        # Fetch tasks assigned to the user
        issues = self.jira.search_issues(
            f'assignee="{assignee}" AND project="{self.jira.project(JIRA_BOARD_SETTINGS.board_name)}"',
        )
        if not issues:
            await query.edit_message_text(f"No tasks found for assignee {assignee}.")
            return ConversationHandler.END

        # Display tasks with priorities
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{issue.key} - {issue.fields.summary} (Priority: {issue.fields.priority.name})",
                    callback_data=issue.key,
                ),
            ]
            for issue in issues
        ]
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Please select a task to view its details:",
            reply_markup=reply_markup,
        )
        return self.TASK_SELECTION

    async def show_task_details(self, update: Update, context: CallbackContext) -> int:
        """Show details of the selected task and provide options to return or continue."""
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.edit_message_text("Task transition process cancelled.")
            return ConversationHandler.END

        task_key = query.data
        issue = self.jira.issue(task_key)
        context.user_data["selected_task"] = issue

        description = issue.fields.description or "No description provided"
        message = (
            f"Task: {task_key}\n"
            f"Summary: {issue.fields.summary}\n"
            f"Description: {description}\n"
            f"Status: {issue.fields.status.name}"
        )

        keyboard = [
            [InlineKeyboardButton("Continue", callback_data="continue")],
            [InlineKeyboardButton("Return", callback_data="return")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup)
        return self.TASK_ACTION

    async def handle_task_action(self, update: Update, context: CallbackContext) -> int:
        """Handle task action: continue to transition or return to task list."""
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.edit_message_text("Task transition process cancelled.")
            return ConversationHandler.END

        if query.data == "return":
            return await self.select_assignee(
                update,
                context,
            )  # Return to task selection

        if query.data == "continue":
            issue = context.user_data.get("selected_task")
            # Transition the issue to another status (example: "In Progress")
            transitions = self.jira.transitions(issue)
            transition_id = next(
                t["id"] for t in transitions if t["name"] == "In Progress"
            )

            if transition_id:
                self.jira.transition_issue(issue, transition_id)
                await query.edit_message_text(
                    f"Task {issue.key} transitioned to 'In Progress'.",
                )
            else:
                await query.edit_message_text(
                    f"No valid transitions found for task {issue.key}.",
                )

            return ConversationHandler.END
