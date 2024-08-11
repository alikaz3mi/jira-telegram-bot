from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from jira import JIRA
from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_BOARD_SETTINGS


class TaskStatus:
    TASK_ID = 1

    def __init__(self, jira: JIRA):
        self.jira = jira
        self.board_settings = JIRA_BOARD_SETTINGS

    async def get_task_status(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text("Please enter the task ID or key:")
        return self.TASK_ID  #

    async def fetch_task_details(self, update: Update, context: CallbackContext) -> int:
        task_id = update.message.text.strip()

        try:
            issues = self.jira.search_issues(
                f"project = '{self.board_settings.board_name}' AND key = '{self.board_settings.board_name}-{task_id}'"
            )

            if not issues:
                await update.message.reply_text(
                    f"No task found with ID {task_id} on board {self.board_settings.board_name}"
                )
                return ConversationHandler.END

            issue = issues[
                0
            ]  # Assuming there's only one result since we're searching by key
            summary = issue.fields.summary
            priority = (
                issue.fields.priority.name if issue.fields.priority else "Not set"
            )
            description = issue.fields.description or "No description"
            assignee = issue.fields.assignee.displayName
            status = issue.fields.status.name
            if (
                issue.fields.customfield_10106 is not None
                and issue.fields.timespent is not None
            ):
                estimated_time = issue.fields.customfield_10106 * 8 - int(
                    issue.fields.timespent / 3600
                )
            else:
                estimated_time = "None"

            response = (
                f"*Summary*: {summary}\n\n"
                f"*Priority*: {priority}\n\n"
                f"*Description*: {description}\n\n"
                f"*Estimated Remaining Time \\(H\\)*: {estimated_time}\n\n"
                f"*Assignee*: {assignee}\n\n"
                f"🔑 *Status*: {status}\n\n"
            )

            await update.message.reply_text(response, parse_mode="MarkdownV2")

        except Exception as e:
            await update.message.reply_text(f"Failed to fetch task details: {str(e)}")
            LOGGER.error("Error fetching task details: %s", e)

        return (
            ConversationHandler.END
        )  # End the conversation after task details are fetched
