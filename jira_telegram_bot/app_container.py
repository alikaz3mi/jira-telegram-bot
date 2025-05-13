"""Application container for Jira Telegram bot."""

import os
from telegram.ext import Application

from lagom import Container, Singleton
from lagom.integrations.fast_api import FastApiIntegration

from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import (
    AdvancedTaskCreation,
)
from jira_telegram_bot.use_cases.telegram_commands.board_summarizer import create_llm_chain
from jira_telegram_bot.use_cases.telegram_commands.board_summarizer import TaskProcessor
from jira_telegram_bot.use_cases.telegram_commands.board_summary_generator import BoardSummaryGenerator
from jira_telegram_bot.use_cases.telegram_commands.create_task import JiraTaskCreation
from jira_telegram_bot.use_cases.telegram_commands.task_get_users_time import TaskGetUsersTime
from jira_telegram_bot.use_cases.telegram_commands.task_status import TaskStatus
from jira_telegram_bot.use_cases.telegram_commands.transition_task import JiraTaskTransition
from jira_telegram_bot.use_cases.telegram_commands.user_settings import UserSettingsConversation
from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AiServiceProtocol,
    PromptCatalogProtocol,
)
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator
from jira_telegram_bot.use_cases.interfaces.story_decomposition_interface import (
    StoryDecompositionInterface,
)
from jira_telegram_bot.use_cases.interfaces.subtask_creation_interface import (
    SubtaskCreationInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


# Global container instance
_container = None


def get_container() -> Container:
    """Get the global container instance.
    
    Returns:
        The configured container
    """
    global _container
    if _container is None:
        _container = setup_container()
    return _container


def setup_container() -> Container:
    """Set up and configure the application container.
    
    Returns:
        Fully configured container
    """
    # Get base container from config
    container = configure_container()
    
    # Create a child container that inherits from the base container
    child_container = Container(container)
    
    # Create LLM chain for board summarization
    llm_chain = create_llm_chain(OPENAI_SETTINGS)
    summary_generator = TaskProcessor(llm_chain)
    
    # Configure Telegram command use cases
    child_container[JiraTaskCreation] = Singleton(
        lambda c: JiraTaskCreation(
            c[TaskManagerRepositoryInterface],
            c[UserConfigInterface]
        )
    )
    
    child_container[TaskStatus] = Singleton(
        lambda c: TaskStatus(
            c[TaskManagerRepositoryInterface].jira
        )
    )
    
    child_container[JiraTaskTransition] = Singleton(
        lambda c: JiraTaskTransition(
            c[TaskManagerRepositoryInterface].jira
        )
    )
    
    child_container[UserSettingsConversation] = Singleton(
        lambda c: UserSettingsConversation(
            c[UserConfigInterface],
            ["alikaz3mi"]  # Admin users
        )
    )
    
    child_container[TaskGetUsersTime] = Singleton(
        lambda c: TaskGetUsersTime(
            c[TaskManagerRepositoryInterface],
            ["alikaz3mi", "hamed_ahmadi1991"]  # Users to track
        )
    )
    
    child_container[BoardSummaryGenerator] = Singleton(
        lambda c: BoardSummaryGenerator(
            c[TaskManagerRepositoryInterface],
            summary_generator
        )
    )
    
    # Advanced Task Creation use case
    child_container[AdvancedTaskCreation] = Singleton(
        lambda c: AdvancedTaskCreation(
            task_manager_repository=c[TaskManagerRepositoryInterface],
            user_config=c[UserConfigInterface],
            ai_service=c[AiServiceProtocol],
            prompt_catalog=c[PromptCatalogProtocol],
            story_generator=c[StoryGenerator],
            story_decomposition_service=c[StoryDecompositionInterface],
            subtask_creation_service=c[SubtaskCreationInterface],
        )
    )
    
    return child_container


def create_telegram_application() -> Application:
    """Create and configure a Telegram bot application.
    
    Returns:
        Configured Telegram Application instance
    """
    application = (
        Application.builder()
        .token(TELEGRAM_SETTINGS.TOKEN)
        .read_timeout(20)
        .connect_timeout(20)
        .build()
    )
    
    return application


def create_fastapi_integration() -> FastApiIntegration:
    """Create FastAPI integration with dependency injection.
    
    Returns:
        FastAPI integration for dependency injection
    """
    container = get_container()
    deps = FastApiIntegration(container)
    return deps


async def startup() -> None:
    """Run startup tasks for the application."""
    LOGGER.info("Starting Jira Telegram Bot application")
    # Add any startup tasks here
    

async def shutdown() -> None:
    """Run shutdown tasks for the application."""
    LOGGER.info("Shutting down Jira Telegram Bot application")
    # Add any cleanup tasks here


def run_app() -> None:
    """Run the Telegram bot application."""
    LOGGER.info("Starting Jira Telegram Bot")
    
    # Get container and create application
    container = get_container()
    application = create_telegram_application()
    
    # App initialization logic can be moved here from __main__.py
    
    # Run telegram application
    application.run_polling()
