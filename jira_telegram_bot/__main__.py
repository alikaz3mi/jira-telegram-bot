import os
import traceback
from pathlib import Path
from warnings import filterwarnings

from telegram.ext import CommandHandler
from telegram.warnings import PTBUserWarning

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container, create_telegram_application, startup
from jira_telegram_bot.frameworks.telegram.advanced_task_creation_handler import (
    AdvancedTaskCreationHandler,
)
from jira_telegram_bot.frameworks.telegram.board_summary_generator_handler import (
    BoardSummaryGeneratorHandler,
)
from jira_telegram_bot.frameworks.telegram.task_creation_handler import (
    TaskCreationHandler,
)
from jira_telegram_bot.frameworks.telegram.task_get_users_time_handler import (
    TaskGetUsersTimeHandler,
)
from jira_telegram_bot.frameworks.telegram.task_status_handler import TaskStatusHandler
from jira_telegram_bot.frameworks.telegram.task_transition_handler import (
    TaskTransitionHandler,
)
from jira_telegram_bot.frameworks.telegram.user_settings_handler import (
    UserSettingsHandler,
)
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import AdvancedTaskCreation
from jira_telegram_bot.use_cases.telegram_commands.board_summary_generator import BoardSummaryGenerator
from jira_telegram_bot.use_cases.telegram_commands.create_task import JiraTaskCreation
from jira_telegram_bot.use_cases.telegram_commands.task_get_users_time import TaskGetUsersTime
from jira_telegram_bot.use_cases.telegram_commands.task_status import TaskStatus
from jira_telegram_bot.use_cases.telegram_commands.transition_task import JiraTaskTransition
from jira_telegram_bot.use_cases.telegram_commands.user_settings import UserSettingsConversation
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor

filterwarnings(
    action="ignore",
    message=r".*CallbackQueryHandler",
    category=PTBUserWarning,
)


async def help_command(update, context):
    """Display help information to the user.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram
    """
    help_text = (
        "Here's how to use this bot:\n\n"
        "1. **/create_task** - Start creating a new task.\n"
        "2. **/transition** - Transition an existing task.\n"
        "3. **/status** - Get the status of a task.\n"
        "4. **/summary_tasks** - Get a summary of completed tasks and tasks that are ready for review\n"
        "5. **/setting** - Update user settings\n"
        "6. **/get_users_time** - Get users' time spent on tasks\n"
        "7. **/advanced_task** - Create multiple related tasks using AI-powered task breakdown\n"
        "8. **/cancel** - Cancel the current running operation"
    )
    await update.message.reply_text(help_text)
    LOGGER.info("Displayed help information")


async def error(update, context):
    """Handle errors that occur during handling of updates.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram containing the error
    """
    LOGGER.warning(f'Update \n\n "{update}" caused error "\n {context.error}"')
    if context.error:
        LOGGER.error(f"Context error details: {context.error}")
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
        LOGGER.error(f"Context error details: {context.error}")

    except Exception as e:
        LOGGER.error(f"Failed to send error message to user or log detail: {e}")
        tb = traceback.extract_tb(e.__traceback__)
        formatted_tb = traceback.format_list(tb)
        for line in formatted_tb:
            LOGGER.error(line)


def ensure_data_directories():
    """Ensure necessary data directories exist."""
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    storage_dir = data_dir / "storage"
    
    # Create data directories if they don't exist
    data_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    LOGGER.info(f"Ensuring data directories exist: {data_dir}")


def setup_and_run():
    """Set up and run the application with proper async handling."""
    # Ensure data directories exist
    ensure_data_directories()
    
    # Get container and dependencies
    container = get_container()
    application = create_telegram_application()
    
    # Get use cases from container
    task_creation_use_case = container[JiraTaskCreation]
    task_status_use_case = container[TaskStatus]
    task_transition_use_case = container[JiraTaskTransition]
    user_settings_use_case = container[UserSettingsConversation]
    task_get_users_time_use_case = container[TaskGetUsersTime]
    board_summary_generator_use_case = container[BoardSummaryGenerator]
    advanced_task_creation_use_case = container[AdvancedTaskCreation]
    speech_processor = container[SpeechProcessor]

    # Create handlers
    task_creation_handler = TaskCreationHandler(task_creation_use_case)
    task_status_handler = TaskStatusHandler(task_status_use_case)
    task_transition_handler = TaskTransitionHandler(task_transition_use_case)
    user_settings_handler = UserSettingsHandler(user_settings_use_case)
    board_summary_generator_handler = BoardSummaryGeneratorHandler(
        board_summary_generator_use_case,
    )
    task_get_users_time_handler = TaskGetUsersTimeHandler(task_get_users_time_use_case)
    advanced_task_creation_handler = AdvancedTaskCreationHandler(
        advanced_task_creation_use_case,
        speech_processor,
    )

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(task_creation_handler.get_handler())
    application.add_handler(task_transition_handler.get_handler())
    application.add_handler(task_status_handler.get_handler())
    application.add_handler(board_summary_generator_handler.get_handler())
    application.add_handler(user_settings_handler.get_handler())
    application.add_handler(task_get_users_time_handler.get_handler())
    application.add_handler(advanced_task_creation_handler.get_handler())
    application.add_error_handler(error)
    startup()
    
    # Start the bot
    LOGGER.info("Starting bot with polling...")
    
    # Configure more options for polling
    application.run_polling(
        allowed_updates=["message", "callback_query", "channel_post"],
        poll_interval=1.0,  # Check for updates every second
        timeout=30,         # Longer timeout for API requests
        drop_pending_updates=True,  # Start fresh on bot restart
        close_loop=False    # Don't close the event loop
    )


def main():
    """Run the Jira Telegram Bot application."""
    try:
        setup_and_run()
    except KeyboardInterrupt:
        LOGGER.info("Application interrupted by user")
    except Exception as e:
        LOGGER.error(f"Application failed with error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
