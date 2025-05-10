from __future__ import annotations

from typing import Dict, Type, Any, TypeVar, Callable

from lagom import Container

from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.ai_models.openai_model import OpenAIGateway
from jira_telegram_bot.adapters.ai_models.gemini_gateway import GeminiGateway
from jira_telegram_bot.adapters.ai_models.speech_processor import SpeechProcessor
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import TelegramGateway
from jira_telegram_bot.adapters.services.telegram.authentication import TelegramAuthentication
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.settings import JIRA_SETTINGS, TELEGRAM_SETTINGS, OPENAI_SETTINGS, GEMINI_SETTINGS
from jira_telegram_bot.use_cases.interfaces.authentication_interface import AuthenticationInterface
from jira_telegram_bot.use_cases.interfaces.llm_interface import LLMInterface
from jira_telegram_bot.use_cases.interfaces.openai_gateway_interface import OpenAIGatewayInterface
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import SpeechProcessorInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.telegram_gateway_interface import TelegramGatewayInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface


T = TypeVar('T')

def configure_dependencies(container: Container) -> None:
    """Configure dependencies in the DI container.
    
    This function configures all dependencies following Clean Architecture principles,
    binding interfaces to their concrete implementations.
    
    Args:
        container: The dependency injection container to configure.
    """
    # Configure adapters with their settings
    _bind_adapters_with_settings(container)
    
    # Configure LLM implementations
    _bind_llm_implementations(container)


def _bind_adapters_with_settings(container: Container) -> None:
    """Bind interfaces to adapters with appropriate settings injection.
    
    Args:
        container: The dependency injection container.
    """
    # Core interfaces -> adapters bindings with settings
    container[TelegramGatewayInterface] = TelegramGateway(settings=TELEGRAM_SETTINGS)
    container[TaskManagerRepositoryInterface] = JiraRepository(settings=JIRA_SETTINGS)
    container[OpenAIGatewayInterface] = OpenAIGateway(settings=OPENAI_SETTINGS)
    container[SpeechProcessorInterface] = SpeechProcessor()
    container[UserConfigInterface] = UserConfig()
    container[AuthenticationInterface] = TelegramAuthentication()


def _bind_llm_implementations(container: Container) -> None:
    """Configure and bind LLM implementations.
    
    Args:
        container: The dependency injection container.
    """
    # Create LLM implementations
    openai_gateway = OpenAIGateway(settings=OPENAI_SETTINGS)
    gemini_gateway = GeminiGateway(settings=GEMINI_SETTINGS)
    
    # Configure default LLM implementation
    container[LLMInterface] = openai_gateway
    
    # Named bindings for specific LLM implementations
    container["openai_llm"] = openai_gateway
    container["gemini_llm"] = gemini_gateway


def register_use_case(container: Container, interface_type: Type[T], 
                      implementation: Type[T], dependencies: Dict[str, Any]) -> None:
    """Register a use case with its dependencies.
    
    This helper function simplifies registering use cases with their dependencies.
    
    Args:
        container: The dependency injection container.
        interface_type: The interface type for the use case.
        implementation: The concrete implementation of the use case.
        dependencies: Dictionary mapping of dependency parameter names to their types.
    """
    def factory(c: Container) -> T:
        kwargs = {name: c[dep_type] for name, dep_type in dependencies.items()}
        return implementation(**kwargs)
    
    container[interface_type] = factory