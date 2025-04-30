from __future__ import annotations

from lagom import Container
from lagom.integrations.fast_api import FastApiIntegration

from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.ai_models.openai_model import OpenAIGateway
from jira_telegram_bot.adapters.ai_models.speech_processor import SpeechProcessor
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import TelegramGateway
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import (
    HandleJiraWebhookUseCase,
)
from jira_telegram_bot.use_cases.interface.openai_gateway_interface import (
    OpenAIGatewayInterface,
)
from jira_telegram_bot.use_cases.interface.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interface.telegram_gateway_interface import (
    TelegramGatewayInterface,
)
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import ParseJiraPromptUseCase


def create_container() -> Container:
    """
    Creates and configures a Lagom DI container, binding
    interfaces to adapters and use cases to their dependencies.
    """
    container = Container()

    #
    # A) Bind INTERFACE -> ADAPTER
    #
    container[TelegramGatewayInterface] = TelegramGateway()
    container[TaskManagerRepositoryInterface] = JiraRepository()
    container[OpenAIGatewayInterface] = OpenAIGateway()
    container[SpeechProcessorInterface] = SpeechProcessor()

    #
    # B) Bind USE CASES, injecting the required interfaces
    #
    container[CreateTaskUseCase] = lambda c: CreateTaskUseCase(
        jira_repo=c[TaskManagerRepositoryInterface],
    )
    container[ParseJiraPromptUseCase] = lambda c: ParseJiraPromptUseCase(
        openai_gateway=c[OpenAIGatewayInterface],
    )
    container[HandleJiraWebhookUseCase] = lambda c: HandleJiraWebhookUseCase(
        telegram_gateway=c[TelegramGatewayInterface],
        speech_processor=c[SpeechProcessorInterface],
    )

    return container


def create_fastapi_integration() -> FastApiIntegration:
    container = create_container()
    deps = FastApiIntegration(container)
    return deps
