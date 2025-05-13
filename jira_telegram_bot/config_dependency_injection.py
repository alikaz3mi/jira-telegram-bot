"""Dependency injection configuration for jira telegram bot."""

import os
from pathlib import Path
from typing import Dict, Any

from lagom import Container, Singleton

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.gemini_settings import GeminiConnectionSetting
from jira_telegram_bot.settings.gitlab_settings import GitlabSettings
from jira_telegram_bot.settings.google_sheets_settings import GoogleSheetsConnectionSettings
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.settings.telegram_settings import (
    TelegramWebhookConnectionSettings,
)

from jira_telegram_bot.adapters.ai_models.llm_models import LLMModels
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import (
    NotificationGateway,
)
from jira_telegram_bot.adapters.repositories.file_storage.prompt_catalog import (
    FilePromptCatalog, 
)
from jira_telegram_bot.adapters.repositories.file_storage.project_info_repository import (
    ProjectInfoRepository
)
from jira_telegram_bot.adapters.ai_models.ai_agents.langchain_ai_agent import (
    LangChainAiService,
)
from jira_telegram_bot.adapters.ai_models.ai_agents.story_generator_service import (
    StoryGeneratorService,
)
from jira_telegram_bot.adapters.ai_models.ai_agents.story_decomposition_service import (
    StoryDecompositionService,
)
from jira_telegram_bot.adapters.ai_models.ai_agents.subtask_creation_service import (
    SubtaskCreationService,
)
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import (
    ParseJiraPromptUseCase,
)
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import (
    HandleJiraWebhookUseCase,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AiServiceProtocol,
    PromptCatalogProtocol,
)
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator
from jira_telegram_bot.use_cases.interfaces.llm_model_interface import (
    LLMModelInterface,
)
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
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
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.adapters.user_config import UserConfig


def read_user_config(config_path: Path) -> Dict[str, Any]:
    """Read user configuration from specified path.
    
    Args:
        config_path: Path to the user configuration directory
        
    Returns:
        Dictionary with user configuration data
    """
    # This is a placeholder - implement actual config reading logic if needed
    try:
        LOGGER.info(f"Reading user configuration from {config_path}")
        # Actual implementation would read from files here
        return {}
    except Exception as e:
        LOGGER.error(f"Error reading user configuration: {str(e)}")
        return {}


def configure_container() -> Container:
    """Configure the dependency injection container.
    
    Returns:
        Configured Lagom container
    """
    container = Container()
    
    # Configure settings
    data_dir = Path(os.environ.get('DATA_DIR', './data'))
    
    # Add settings to container
    container[JiraConnectionSettings] = Singleton(lambda: JiraConnectionSettings())
    container[TelegramConnectionSettings] = Singleton(lambda: TelegramConnectionSettings())
    container[TelegramWebhookConnectionSettings] = Singleton(lambda: TelegramWebhookConnectionSettings())
    container[OpenAISettings] = Singleton(lambda: OpenAISettings())
    container[GeminiConnectionSetting] = Singleton(lambda: GeminiConnectionSetting())
    container[GitlabSettings] = Singleton(lambda: GitlabSettings())
    container[PostgresSettings] = Singleton(lambda: PostgresSettings())
    container[JiraBoardSettings] = Singleton(lambda: JiraBoardSettings())
    
    # Add GoogleSheetsSettings if it exists
    try:
        container[GoogleSheetsConnectionSettings] = Singleton(lambda: GoogleSheetsConnectionSettings())
    except Exception as e:
        LOGGER.warning(f"GoogleSheetsConnectionSettings not registered: {e}")
    
    # A) Bind INTERFACE -> ADAPTER
    container[NotificationGatewayInterface] = Singleton(
        lambda c: NotificationGateway(c[TelegramConnectionSettings])
    )
    
    container[TaskManagerRepositoryInterface] = Singleton(
        lambda c: JiraServerRepository(c[JiraConnectionSettings])
    )
    
    container[ProjectInfoRepositoryInterface] = Singleton(
        lambda c: ProjectInfoRepository()
    )
    
    container[LLMModelInterface] = Singleton(
        lambda c: LLMModels(
            c[OpenAISettings],
            c[GeminiConnectionSetting]
        )
    )
    
    container[SpeechProcessorInterface] = Singleton(
        lambda c: SpeechProcessor(
            c[OpenAISettings],
        )
    )
    
    # AI Service bindings
    container[AiServiceProtocol] = Singleton(
        lambda c: LangChainAiService(
            c[LLMModelInterface]
        )
    )
    
    container[PromptCatalogProtocol] = Singleton(
        lambda c: FilePromptCatalog()
    )
    
    container[StoryGenerator] = Singleton(
        lambda c: StoryGeneratorService(
            c[AiServiceProtocol],
            c[PromptCatalogProtocol]
        )
    )
    
    container[StoryDecompositionInterface] = Singleton(
        lambda c: StoryDecompositionService(
            c[AiServiceProtocol],
            c[PromptCatalogProtocol]
        )
    )
    
    container[SubtaskCreationInterface] = Singleton(
        lambda c: SubtaskCreationService(
            c[AiServiceProtocol],
            c[PromptCatalogProtocol]
        )
    )
    
    container[UserConfigInterface] = Singleton(
        lambda c: UserConfig(
            user_config_path=str(data_dir / "storage" / "user_config.json")
        )
    )

    # B) Bind basic USE CASES
    container[CreateTaskUseCase] = Singleton(
        lambda c: CreateTaskUseCase(
            jira_repo=c[TaskManagerRepositoryInterface],
        )
    )
    
    container[ParseJiraPromptUseCase] = Singleton(
        lambda c: ParseJiraPromptUseCase(
            openai_gateway=c[LLMModelInterface],
        )
    )
    
    container[HandleJiraWebhookUseCase] = Singleton(
        lambda c: HandleJiraWebhookUseCase(
            telegram_gateway=c[NotificationGatewayInterface],
        )
    )
    
    return container


