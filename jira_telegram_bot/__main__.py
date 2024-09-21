from __future__ import annotations

from jira import JIRA
from telegram import Update
from telegram.ext import Application
from telegram.ext import CallbackContext
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS
from jira_telegram_bot.use_cases.authentication import check_user_allowed
from jira_telegram_bot.use_cases.create_task import JiraTaskCreation
from jira_telegram_bot.use_cases.task_status import TaskStatus
from jira_telegram_bot.use_cases.transition_task import JiraTaskTransition

jira = JIRA(
    server=JIRA_SETTINGS.domain,
    basic_auth=(JIRA_SETTINGS.username, JIRA_SETTINGS.password),
)

jira_task_creation = JiraTaskCreation(jira)
jira_task_transition = JiraTaskTransition(jira)
jira_task_status = TaskStatus(jira)


async def start(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    LOGGER.info(
        f"Starting task creation process in chat type: {update.message.chat.type}",
    )
    # Start the project selection step
    return await jira_task_creation.select_project(update, context)


# Add this function to handle the /status command
async def start_status(update: Update, context: CallbackContext) -> int:
    """Start the task status retrieval process."""
    return await jira_task_status.get_task_status(update, context)


async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Here's how to use this bot to create a Jira task:\n\n"
        "1. **/start**: Start the process of creating a new task.\n"
        "2. **/transition**: Start the process of transitioning an existing task to another state.\n"
        "3. **/status**: Get the status of a task by giving the task number.\n"
        "4. **Project Selection**: Choose the project where you want to create the task.\n"
        "5. **Summary**: Send the summary of the task when prompted.\n"
        "6. **Description**: Send the description of the task when prompted, or type 'skip' to skip this step.\n"
        "7. **Component**: Choose the component for the task from the list provided.\n"
        "8. **Assignee**: Choose an assignee for the task from the list provided, or type 'skip' to skip.\n"
        "9. **Priority**: Choose a priority for the task from the list provided, or type 'skip' to skip.\n"
        "10. **Sprint**: Choose the sprint or backlog for the task.\n"
        "11. **Epic**: Choose an epic for the task from the list provided, or type 'skip' to skip.\n"
        "12. **Task Type**: Choose the type of the task.\n"
        "13. **Image**: Send one or more images related to the task.\n\n"
        "The bot will then create a new Jira task with the provided details and attach the images to the task."
    )
    await update.message.reply_text(help_text)
    LOGGER.info("Displayed help information")


async def terminate(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Task creation process terminated.")
    LOGGER.info("Task creation process terminated")
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Operation cancelled.")
    LOGGER.info("Operation cancelled by user")
    return ConversationHandler.END


async def error(update: Update, context: CallbackContext) -> None:
    LOGGER.warning('Update "%s" caused error "%s"', update, context.error)

    try:
        if update.message:
            await update.message.reply_text(f"An error occurred: {context.error}")
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                f"An error occurred: {context.error}",
            )
    except Exception as e:
        LOGGER.error("Failed to send error message to user: %s", e)


async def start_transition(update: Update, context: CallbackContext) -> int:
    """Start the task transition process."""
    return await jira_task_transition.start_transition(update, context)


def main() -> None:
    application = (
        Application.builder()
        .token(TELEGRAM_SETTINGS.TOKEN)
        .read_timeout(20)
        .connect_timeout(20)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            jira_task_creation.PROJECT: [
                CallbackQueryHandler(jira_task_creation.select_project_callback),
            ],
            jira_task_creation.SUMMARY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    jira_task_creation.add_summary,
                ),
            ],
            jira_task_creation.DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    jira_task_creation.add_description,
                ),
            ],
            jira_task_creation.COMPONENT: [
                CallbackQueryHandler(jira_task_creation.button_component),
            ],
            jira_task_creation.ASSIGNEE: [
                CallbackQueryHandler(jira_task_creation.button_assignee),
            ],
            jira_task_creation.PRIORITY: [
                CallbackQueryHandler(jira_task_creation.button_priority),
            ],
            jira_task_creation.SPRINT: [
                CallbackQueryHandler(jira_task_creation.button_sprint),
            ],
            jira_task_creation.EPIC: [
                CallbackQueryHandler(jira_task_creation.button_epic),
            ],
            jira_task_creation.TASK_TYPE: [
                CallbackQueryHandler(jira_task_creation.button_task_type),
            ],
            jira_task_creation.STORY_SELECTION: [
                CallbackQueryHandler(jira_task_creation.button_story_selection),
            ],
            jira_task_creation.STORY_POINTS: [
                CallbackQueryHandler(jira_task_creation.button_story_points),
            ],
            jira_task_creation.IMAGE: [
                MessageHandler(
                    filters.PHOTO | (filters.TEXT & ~filters.COMMAND),
                    jira_task_creation.handle_image,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("terminate", terminate),
        ],
    )

    # Task transition handler
    transition_handler = ConversationHandler(
        entry_points=[CommandHandler("transition", start_transition)],
        states={
            jira_task_transition.ASSIGNEE: [
                CallbackQueryHandler(jira_task_transition.select_assignee),
            ],
            jira_task_transition.TASK_SELECTION: [
                CallbackQueryHandler(jira_task_transition.show_task_details),
            ],
            jira_task_transition.TASK_ACTION: [
                CallbackQueryHandler(jira_task_transition.handle_task_action),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("terminate", terminate),
        ],
    )

    status_handler = ConversationHandler(
        entry_points=[CommandHandler("status", start_status)],
        states={
            jira_task_status.TASK_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    jira_task_status.fetch_task_details,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("terminate", terminate),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(transition_handler)
    application.add_handler(status_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error)

    LOGGER.info("Starting bot")
    application.run_polling()


if __name__ == "__main__":
    main()
