from __future__ import annotations

from lagom import Container
from lagom.integrations.fast_api import FastApiIntegration

from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.ai_models.openai_model import OpenAIGateway
from jira_telegram_bot.adapters.ai_models.gemini_gateway import GeminiGateway
from jira_telegram_bot.adapters.ai_models.speech_processor import SpeechProcessor
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import TelegramGateway
from jira_telegram_bot.adapters.services.telegram.authentication import TelegramAuthentication
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.config_dependency_injection import configure_dependencies, register_use_case
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import (
    HandleJiraWebhookUseCase,
)
from jira_telegram_bot.use_cases.interfaces.authentication_interface import AuthenticationInterface
from jira_telegram_bot.use_cases.interfaces.llm_interface import LLMInterface
from jira_telegram_bot.use_cases.interfaces.openai_gateway_interface import (
    OpenAIGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.telegram_gateway_interface import (
    TelegramGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import ParseJiraPromptUseCase
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import AdvancedTaskCreation


def create_container() -> Container:
    """Create and configure a Lagom DI container.
    
    Creates and configures a Lagom DI container, binding
    interfaces to adapters and use cases to their dependencies.
    
    Returns:
        A configured dependency injection container.
    """
    container = Container()

    # Configure all dependencies from the configuration module
    configure_dependencies(container)

    # Register use cases with their dependencies
    _register_use_cases(container)

    return container


def _register_use_cases(container: Container) -> None:
    """Register all use cases with their required dependencies.
    
    Args:
        container: The dependency injection container.
    """
    # Register core use cases using the helper function
    register_use_case(
        container,
        CreateTaskUseCase,
        CreateTaskUseCase,
        {"jira_repo": TaskManagerRepositoryInterface}
    )
    
    register_use_case(
        container,
        ParseJiraPromptUseCase,
        ParseJiraPromptUseCase,
        {"openai_gateway": OpenAIGatewayInterface}
    )
    
    register_use_case(
        container,
        HandleJiraWebhookUseCase,
        HandleJiraWebhookUseCase,
        {
            "telegram_gateway": TelegramGatewayInterface,
            "speech_processor": SpeechProcessorInterface
        }
    )
    
    # Special case: use case needs a specific named implementation
    def advanced_task_factory(c: Container) -> AdvancedTaskCreation:
        return AdvancedTaskCreation(
            jira_repo=c[TaskManagerRepositoryInterface],
            user_config=c[UserConfigInterface],
            llm_service=c["gemini_llm"]  # Using the named Gemini implementation
        )
    
    container[AdvancedTaskCreation] = advanced_task_factory


def create_fastapi_integration() -> FastApiIntegration:
    """Create a FastAPI integration with the configured container.
    
    Returns:
        A FastAPI integration instance with dependency injection support.
    """
    container = create_container()
    deps = FastApiIntegration(container)
    return deps
