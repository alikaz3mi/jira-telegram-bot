from __future__ import annotations

from lagom import Container
from lagom import Singleton
from lagom.integrations.fast_api import FastApiIntegration

from jira_telegram_bot.adapters.ai_models.llm_models import LLMModels
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraRepository,
)
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import (
    NotificationGateway,
)
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import (
    ParseJiraPromptUseCase,
)
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import (
    HandleJiraWebhookUseCase,
)
from jira_telegram_bot.use_cases.interfaces.llm_model_interface import (
    LLMModelInterface,
)
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


def create_container() -> Container:
    """
    Creates and configures a Lagom DI container, binding
    interfaces to adapters and use cases to their dependencies.
    """
    container = Container()

    #
    # A) Bind INTERFACE -> ADAPTER
    #
    container[NotificationGatewayInterface] = Singleton(NotificationGateway)
    container[TaskManagerRepositoryInterface] = Singleton(JiraRepository)
    container[LLMModelInterface] = Singleton(LLMModels)
    container[SpeechProcessorInterface] = Singleton(SpeechProcessor)

    #
    # B) Bind USE CASES, injecting the required interfaces
    #
    container[CreateTaskUseCase] = lambda c: CreateTaskUseCase(
        jira_repo=c[TaskManagerRepositoryInterface],
    )
    container[ParseJiraPromptUseCase] = lambda c: ParseJiraPromptUseCase(
        openai_gateway=c[LLMModelInterface],
    )
    container[HandleJiraWebhookUseCase] = lambda c: HandleJiraWebhookUseCase(
        telegram_gateway=c[NotificationGatewayInterface],
    )

    return container


def create_fastapi_integration() -> FastApiIntegration:
    container = create_container()
    deps = FastApiIntegration(container)
    return deps
