from telegram import (
    Update,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    Application,
    ConversationHandler,
    CallbackQueryHandler,
)
from jira import JIRA

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.authentication import check_user_allowed
from jira_telegram_bot.use_cases.create_task import (
    handle_image,
    add_description,
    add_summary,
    button_assignee,
    button_component,
    button_epic,
    button_priority,
    button_sprint,
    button_story_points,
    button_task_type,
    SUMMARY,
    DESCRIPTION,
    COMPONENT,
    ASSIGNEE,
    PRIORITY,
    SPRINT,
    EPIC,
    TASK_TYPE,
    STORY_POINTS,
    IMAGE,
)

from jira_telegram_bot.settings import JIRA_SETTINGS, TELEGRAM_SETTINGS


jira = JIRA(
    server=JIRA_SETTINGS.domain,
    basic_auth=(JIRA_SETTINGS.username, JIRA_SETTINGS.password),
)


async def start(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "Hi! Send me the summary of the task. Type /help for more instructions."
    )
    LOGGER.info(
        f"Starting task creation process in chat type: {update.message.chat.type}"
    )
    return SUMMARY


async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Here's how to use this bot to create a Jira task:\n\n"
        "1. **/start**: Start the process of creating a new task.\n"
        "2. **Summary**: Send the summary of the task when prompted.\n"
        "3. **Description**: Send the description of the task when prompted, or type 'skip' to skip this step.\n"
        "4. **Component**: Choose the component for the task from the list provided.\n"
        "5. **Assignee**: Choose an assignee for the task from the list provided, or type 'skip' to skip.\n"
        "6. **Priority**: Choose a priority for the task from the list provided, or type 'skip' to skip.\n"
        "7. **Sprint**: Choose the sprint or backlog for the task.\n"
        "8. **Epic**: Choose an epic for the task from the list provided, or type 'skip' to skip.\n"
        "9. **Task Type**: Choose the type of the task.\n"
        "10. **Image**: Send one or more images related to the task.\n\n"
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
                f"An error occurred: {context.error}"
            )
    except Exception as e:
        LOGGER.error("Failed to send error message to user: %s", e)


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
            SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_summary)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)
            ],
            COMPONENT: [CallbackQueryHandler(button_component)],
            ASSIGNEE: [CallbackQueryHandler(button_assignee)],
            PRIORITY: [CallbackQueryHandler(button_priority)],
            SPRINT: [CallbackQueryHandler(button_sprint)],
            EPIC: [CallbackQueryHandler(button_epic)],
            TASK_TYPE: [CallbackQueryHandler(button_task_type)],
            STORY_POINTS: [CallbackQueryHandler(button_story_points)],
            IMAGE: [MessageHandler(filters.PHOTO | filters.TEXT, handle_image)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("terminate", terminate),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error)

    LOGGER.info("Starting bot")
    application.run_polling()


if __name__ == "__main__":
    main()
