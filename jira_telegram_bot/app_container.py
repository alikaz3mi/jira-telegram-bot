"""Application container for Jira Telegram bot."""

import os
import asyncio
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
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AiServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
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
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)


# Global container instance
_container = None
_application = None


def get_container() -> Container:
    """Get the global container instance.
    
    Returns:
        The configured container
    """
    global _container
    if (_container is None):
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
    llm_chain = create_llm_chain(container[OpenAISettings])
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
            project_info_repository=c[ProjectInfoRepositoryInterface],
            story_generator= c[StoryGenerator],
            story_decomposition_service=c[StoryDecompositionInterface],
            subtask_creation_service=c[SubtaskCreationInterface],
        )
    )
    
    # Make SpeechProcessor available directly from container
    child_container[SpeechProcessor] = Singleton(
        lambda c: c[SpeechProcessorInterface]
    )
    
    return child_container


def create_telegram_application() -> Application:
    """Create and configure a Telegram bot application.
    
    Returns:
        Configured Telegram Application instance
    """
    global _application
    
    if _application is None:
        _application = (
            Application.builder()
            .token(_container[TelegramConnectionSettings].TOKEN)
            .read_timeout(20)
            .connect_timeout(20)
            .build()
        )
    
    return _application


def create_fastapi_integration() -> FastApiIntegration:
    """Create FastAPI integration with dependency injection.
    
    Returns:
        FastAPI integration for dependency injection
    """
    container = get_container()
    deps = FastApiIntegration(container)
    return deps


def startup() -> None:
    """Run startup tasks for the application."""
    LOGGER.info("Starting Jira Telegram Bot application")
    
    # Initialize container to trigger creation of services
    container = get_container()
    
    # Initialize key services that might need startup procedures
    try:
        # Initialize repository connections
        jira_repo = container[TaskManagerRepositoryInterface]
        LOGGER.info("Initialized Jira repository connection")
        
        # Initialize AI services
        ai_service = container[AiServiceProtocol]
        LOGGER.info("Initialized AI service")
        
        # Initialize speech processor service
        speech_processor = container[SpeechProcessorInterface]
        LOGGER.info("Initialized speech processor service")
        
        # Initialize other potential stateful services
        user_config = container[UserConfigInterface]
        LOGGER.info("Initialized user configuration service")
        
    except Exception as e:
        LOGGER.error(f"Error during startup: {str(e)}")
        raise


async def shutdown() -> None:
    """Run shutdown tasks for the application."""
    LOGGER.info("Shutting down Jira Telegram Bot application")
    
    container = get_container()
    
    # Properly close connections and resources
    try:
        # Clean up Jira connection if needed
        jira_repo = container[TaskManagerRepositoryInterface]
        if hasattr(jira_repo, 'close') and callable(getattr(jira_repo, 'close')):
            await jira_repo.close()
            LOGGER.info("Closed Jira repository connection")
        
        # Clean up AI service connections if needed
        ai_service = container[AiServiceProtocol]
        if hasattr(ai_service, 'close') and callable(getattr(ai_service, 'close')):
            await ai_service.close()
            LOGGER.info("Closed AI service connection")
        
        # Clean up speech processor connections if needed
        speech_processor = container[SpeechProcessorInterface]
        if hasattr(speech_processor, 'close') and callable(getattr(speech_processor, 'close')):
            await speech_processor.close()
            LOGGER.info("Closed speech processor connection")
        
    except Exception as e:
        LOGGER.error(f"Error during shutdown: {str(e)}")
