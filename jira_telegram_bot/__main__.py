from __future__ import annotations

from telegram.ext import Application
from telegram.ext import CommandHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.frameworks.telegram.create_easy_task_handler import (
    EasyTaskHandler,
)
from jira_telegram_bot.frameworks.telegram.task_creation_handler import (
    TaskCreationHandler,
)
from jira_telegram_bot.frameworks.telegram.task_status_handler import TaskStatusHandler
from jira_telegram_bot.frameworks.telegram.task_transition_handler import (
    TaskTransitionHandler,
)
from jira_telegram_bot.settings import TELEGRAM_SETTINGS
from jira_telegram_bot.use_cases.create_easy_task import JiraEasyTaskCreation
from jira_telegram_bot.use_cases.create_task import JiraTaskCreation
from jira_telegram_bot.use_cases.task_status import TaskStatus
from jira_telegram_bot.use_cases.transition_task import JiraTaskTransition


async def help_command(update, context):
    help_text = (
        "Here's how to use this bot:\n\n"
        "1. **/start** - Start creating a new task.\n"
        "2. **/transition** - Transition an existing task.\n"
        "3. **/status** - Get the status of a task.\n"
        "4. **/create-easy-task** - Quickly create a task with predefined settings."
        "5. **/cancel** - cancel current running operation"
    )
    await update.message.reply_text(help_text)
    LOGGER.info("Displayed help information")


async def error(update, context):
    LOGGER.warning('Update "%s" caused error "%s"', update, context.error)
    if context.error:
        LOGGER.error("Context error details: %s", context.error)
    else:
        LOGGER.error("An unknown error occurred in the context.")

    try:
        # Check if `update` contains a message and reply if possible
        if update and hasattr(update, "message") and update.message:
            await update.message.reply_text("An error occurred.")
        elif update and hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.message.reply_text("An error occurred.")
        else:
            # Log an error when there's no user context available
            LOGGER.error(
                "Error occurred without an associated update or callback context.",
            )

        # Log detailed information about the context error
        LOGGER.error("Context error details: %s", context.error)

    except Exception as e:
        LOGGER.error("Failed to send error message to user or log detail")


def main():
    application = (
        Application.builder()
        .token(TELEGRAM_SETTINGS.TOKEN)
        .read_timeout(20)
        .connect_timeout(20)
        .build()
    )

    jira_repo = JiraRepository().jira
    user_config_instance = UserConfig()

    easy_task_use_case = JiraEasyTaskCreation(jira_repo, user_config_instance)
    task_creation_use_case = JiraTaskCreation(jira_repo)
    task_status_use_case = TaskStatus(jira_repo)
    task_transition_use_case = JiraTaskTransition(jira_repo)

    easy_task_handler = EasyTaskHandler(easy_task_use_case)
    task_creation_handler = TaskCreationHandler(task_creation_use_case)
    task_status_handler = TaskStatusHandler(task_status_use_case)
    task_transition_handler = TaskTransitionHandler(task_transition_use_case)

    application.add_handler(task_creation_handler.get_handler())
    application.add_handler(task_transition_handler.get_handler())
    application.add_handler(task_status_handler.get_handler())
    application.add_handler(easy_task_handler.get_handler())
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error)

    LOGGER.info("Starting bot")
    application.run_polling()


if __name__ == "__main__":
    main()
