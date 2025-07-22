"""Application container for Jira Telegram bot."""

import os
import asyncio
from telegram.ext import Application

from lagom import Container, Singleton
from lagom.integrations.fast_api import FastApiIntegration

from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.adapters.services.telegram.authentication import TelegramAuthenticationService
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import (
    AdvancedTaskCreation,
)
from jira_telegram_bot.use_cases.ai_agents.create_subtasks import CreateSubtasksUseCase
from jira_telegram_bot.use_cases.generate_user_story import GenerateUserStoryUseCase

from jira_telegram_bot.use_cases.telegram_commands.board_summary_generator import BoardSummaryGenerator
from jira_telegram_bot.use_cases.ai_agents.board_summarizer import BoardSummarizerUseCase
from jira_telegram_bot.use_cases.telegram_commands.create_task import JiraTaskCreation
from jira_telegram_bot.use_cases.telegram_commands.task_get_users_time import TaskGetUsersTime
from jira_telegram_bot.use_cases.telegram_commands.task_status import TaskStatus
from jira_telegram_bot.use_cases.telegram_commands.transition_task import JiraTaskTransition
from jira_telegram_bot.use_cases.telegram_commands.user_settings import UserSettingsConversation
from jira_telegram_bot.use_cases.telegram_commands.get_current_stories import GetCurrentStoriesUseCase
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AIServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGeneratorInterface
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.ai_agents.story_decomposition import StoryDecompositionUseCase
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_authentication_interface import (
    UserAuthenticationInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)

# Telegram handlers
from jira_telegram_bot.frameworks.telegram.advanced_task_creation_handler import (
    AdvancedTaskCreationHandler,
)
from jira_telegram_bot.frameworks.telegram.board_summary_generator_handler import (
    BoardSummaryGeneratorHandler,
)
from jira_telegram_bot.frameworks.telegram.daily_report_handler import (
    DailyReportHandler,
)
from jira_telegram_bot.frameworks.telegram.task_creation_handler import (
    TaskCreationHandler,
)
from jira_telegram_bot.frameworks.telegram.task_get_users_time_handler import (
    TaskGetUsersTimeHandler,
)
from jira_telegram_bot.frameworks.telegram.task_status_handler import (
    TaskStatusHandler,
)
from jira_telegram_bot.frameworks.telegram.task_transition_handler import (
    TaskTransitionHandler,
)
from jira_telegram_bot.frameworks.telegram.user_settings_handler import (
    UserSettingsHandler,
)
from jira_telegram_bot.frameworks.telegram.get_current_stories_handler import (
    GetCurrentStoriesHandler,
)
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints
from jira_telegram_bot.frameworks.api.endpoints import JiraWebhookEndpoint, TelegramWebhookEndpoint, MetricsWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints.health_check import HealthCheckEndpoint
from jira_telegram_bot.frameworks.api.endpoints.project_status import ProjectStatusEndpoint


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
    
    # Authentication service
    child_container[TelegramAuthenticationService] = Singleton(
        lambda c: TelegramAuthenticationService(
            c[UserAuthenticationInterface]
        )
    )
    
    # Configure Telegram command use cases
    child_container[JiraTaskCreation] = Singleton(
        lambda c: JiraTaskCreation(
            c[TaskManagerRepositoryInterface],
            c[UserConfigInterface]
        )
    )
    
    child_container[TaskStatus] = Singleton(
        lambda c: TaskStatus(
            c[TaskManagerRepositoryInterface]
        )
    )
    
    child_container[JiraTaskTransition] = Singleton(
        lambda c: JiraTaskTransition(
            c[TaskManagerRepositoryInterface]
        )
    )
    
    child_container[UserSettingsConversation] = Singleton(
        lambda c: UserSettingsConversation(
            c[UserConfigInterface],
            ["alikaz3mi"],
            c[UserAuthenticationInterface]
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
            c[BoardSummarizerUseCase],
            c[UserAuthenticationInterface]
        )
    )
    
    # Advanced Task Creation use case
    child_container[AdvancedTaskCreation] = Singleton(
        lambda c: AdvancedTaskCreation(
            task_manager_repository=c[TaskManagerRepositoryInterface],
            user_config=c[UserConfigInterface],
            project_info_repository=c[ProjectInfoRepositoryInterface],
            story_generator=c[GenerateUserStoryUseCase],
            story_decomposition_usecase=c[StoryDecompositionUseCase],
            subtask_creation_usecase=c[CreateSubtasksUseCase],
        )
    )
    
    # Make SpeechProcessor available directly from container
    child_container[SpeechProcessor] = Singleton(
        lambda c: c[SpeechProcessorInterface]
    )
    
    # Configure Telegram handlers
    child_container[TaskCreationHandler] = Singleton(
        lambda c: TaskCreationHandler(c[JiraTaskCreation])
    )
    
    child_container[TaskStatusHandler] = Singleton(
        lambda c: TaskStatusHandler(c[TaskStatus])
    )
    
    child_container[TaskTransitionHandler] = Singleton(
        lambda c: TaskTransitionHandler(c[JiraTaskTransition])
    )
    
    child_container[UserSettingsHandler] = Singleton(
        lambda c: UserSettingsHandler(c[UserSettingsConversation])
    )
    
    child_container[TaskGetUsersTimeHandler] = Singleton(
        lambda c: TaskGetUsersTimeHandler(c[TaskGetUsersTime])
    )
    
    child_container[BoardSummaryGeneratorHandler] = Singleton(
        lambda c: BoardSummaryGeneratorHandler(c[BoardSummaryGenerator])
    )
    
    child_container[AdvancedTaskCreationHandler] = Singleton(
        lambda c: AdvancedTaskCreationHandler(
            c[AdvancedTaskCreation],
            c[SpeechProcessor]
        )
    )
    
    child_container[GetCurrentStoriesHandler] = Singleton(
        lambda c: GetCurrentStoriesHandler(
            get_current_stories_use_case=c[GetCurrentStoriesUseCase],
            jira_settings=c[JiraConnectionSettings],
        )
    )
    
    # Get the endpoint registry
    endpoint_registry = child_container[SubServiceEndpoints]
    
    # # Register API endpoints
    endpoint_registry.register(child_container[JiraWebhookEndpoint])
    endpoint_registry.register(child_container[TelegramWebhookEndpoint])
    endpoint_registry.register(child_container[HealthCheckEndpoint])
    endpoint_registry.register(child_container[ProjectStatusEndpoint])
    endpoint_registry.register(child_container[MetricsWebhookEndpoint])
    
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


def create_fastapi_integration():
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
        ai_service = container[AIServiceProtocol]
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
        ai_service = container[AIServiceProtocol]
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
