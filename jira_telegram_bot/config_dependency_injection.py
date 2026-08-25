"""Dependency injection configuration for jira telegram bot."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from typing import Dict

from lagom import Container
from lagom import Singleton

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.ai_models.ai_agents.langchain_ai_agent import (
    LangChainAiService,
)
from jira_telegram_bot.adapters.ai_models.llm_models import LLMModels
from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.adapters.controllers.gitlab_webhook_controller import (
    GitlabWebhookController,
)
from jira_telegram_bot.adapters.controllers.jira_webhook_controller import (
    JiraWebhookController,
)
from jira_telegram_bot.adapters.gateways.google_sheets.google_sheets_gateway import (
    GoogleSheetsGateway,
)
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.adapters.repositories.file_storage.file_notification_log_repository import (
    FileNotificationLogRepository,
)
from jira_telegram_bot.adapters.repositories.file_storage.file_progress_report_repository import (
    FileProgressReportRepository,
)
from jira_telegram_bot.adapters.repositories.file_storage.metrics.file_user_setting_configuration_repository import (
    FileUserSettingConfigurationRepository,
)
from jira_telegram_bot.adapters.repositories.file_storage.project_info_repository import (
    ProjectInfoRepository,
)
from jira_telegram_bot.adapters.repositories.file_storage.prompt_catalog import (
    FilePromptCatalog,
)
from jira_telegram_bot.adapters.repositories.file_storage.user_authentication_repository import (
    FileUserAuthenticationRepository,
)
from jira_telegram_bot.adapters.repositories.jira.jira_cloud_repository import (
    JiraCloudRepository,
)
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)
from jira_telegram_bot.adapters.repositories.postgres.database.postgresql_connection import (
    PostgreSQLConnection,
)
from jira_telegram_bot.adapters.repositories.postgres.jira_report_repository import (
    JiraReportRepository,
)
from jira_telegram_bot.adapters.repositories.postgres.team_evaluation_repository import (
    PostgresTeamEvaluationRepository,
)
from jira_telegram_bot.adapters.repositories.postgres.team_evaluation_calculation_log_repository import (
    PostgreSQLTeamEvaluationCalculationLogRepository,
)
from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)
from jira_telegram_bot.adapters.services.application_startup_service import (
    ApplicationStartupService,
)
from jira_telegram_bot.adapters.services.current_stories_service import (
    CurrentStoriesService,
)
from jira_telegram_bot.adapters.services.jira_data_service import JiraDataService
from jira_telegram_bot.adapters.services.metrics.metrics_processor_service import (
    MetricsProcessorService,
)
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import (
    NotificationGateway,
)
from jira_telegram_bot.adapters.services.telegram.telegram_notifier import (
    TelegramNotifier,
)
from jira_telegram_bot.adapters.services.xlsx_report_service import XlsxReportService
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.frameworks.api.endpoints import JiraWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints import MetricsWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints import TelegramWebhookEndpoint
from jira_telegram_bot.frameworks.api.endpoints.health_check import HealthCheckEndpoint
from jira_telegram_bot.frameworks.api.endpoints.project_status import (
    ProjectStatusEndpoint,
)
from jira_telegram_bot.frameworks.api.endpoints.synth_pm_endpoint import SynthPMEndpoint
from jira_telegram_bot.frameworks.api.entry_point import FastAPIConfig
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints
from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import (
    APSchedulerService,
)
from jira_telegram_bot.settings.deadline_notifier_settings import (
    DeadlineNotifierSettings,
)
from jira_telegram_bot.settings.fast_api_settings import FastAPISettings
from jira_telegram_bot.settings.gemini_settings import GeminiConnectionSetting
from jira_telegram_bot.settings.gitlab_settings import GitlabSettings
from jira_telegram_bot.settings.google_sheets_settings import (
    GoogleSheetsConnectionSettings,
)
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.jira_settings import JiraConnectionType
from jira_telegram_bot.settings.jira_sync_settings import JiraSyncSettings
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.settings.telegram_settings import (
    TelegramWebhookConnectionSettings,
)
from jira_telegram_bot.use_cases.ai_agents.agent_generate_use_story import (
    AgentGenerateUserStory,
)
from jira_telegram_bot.use_cases.ai_agents.board_summarizer import (
    BoardSummarizerUseCase,
)
from jira_telegram_bot.use_cases.ai_agents.board_summarizer import TaskGrouper
from jira_telegram_bot.use_cases.ai_agents.create_subtasks import CreateSubtasksUseCase
from jira_telegram_bot.use_cases.ai_agents.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaUseCase,
)
from jira_telegram_bot.use_cases.ai_agents.generate_progress_report_usecase import (
    GenerateProgressReportUseCase,
)
from jira_telegram_bot.use_cases.ai_agents.generate_test_scenarios import (
    GenerateTestScenariosUseCase,
)
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import (
    ParseJiraPromptUseCase,
)
from jira_telegram_bot.use_cases.ai_agents.story_decomposition import (
    StoryDecompositionUseCase,
)
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.generate_jira_report_use_case import (
    GenerateJiraReportUseCase,
)
from jira_telegram_bot.use_cases.generate_user_story import GenerateUserStoryUseCase
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import (
    HandleJiraWebhookUseCase,
)
from jira_telegram_bot.use_cases.sync_jira_issue_use_case import SyncJiraIssueUseCase
from jira_telegram_bot.use_cases.calculate_actual_dates_use_case import (
    CalculateActualDatesUseCase,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AIServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import (
    CalendarRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.current_stories_service_interface import (
    CurrentStoriesServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import (
    JiraDataServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import (
    JiraReportRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.llm_model_interface import LLMModelInterface
from jira_telegram_bot.use_cases.interfaces.metrics.metrics_processor_interface import (
    MetricsProcessorInterface,
)
from jira_telegram_bot.use_cases.interfaces.metrics.spreadsheet_gateway_interface import (
    SpreadsheetGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.metrics.user_setting_configuration_repository_interface import (
    UserSettingConfigurationRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.notification_log_repository_interface import (
    NotificationLogRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.progress_report_repository_interface import (
    ProgressReportRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.scheduler_service_interface import (
    SchedulerServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.interfaces.synth_pm_repository_interface import (
    SynthPMRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.telegram_notifier_interface import (
    TelegramNotifierInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_authentication_interface import (
    UserAuthenticationInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.interfaces.xlsx_report_service_interface import (
    XlsxReportServiceInterface,
)
from jira_telegram_bot.use_cases.metrics.process_gitlab_event_use_case import (
    ProcessGitlabEventUseCase,
)
from jira_telegram_bot.use_cases.metrics.process_jira_event_use_case import (
    ProcessJiraEventUseCase,
)
from jira_telegram_bot.use_cases.metrics.update_sheet_use_case import UpdateSheetUseCase
from jira_telegram_bot.use_cases.project_status import GetProjectStatusUseCase
from jira_telegram_bot.use_cases.project_status import UpdateProjectTrackingUseCase
from jira_telegram_bot.use_cases.scheduled_report_use_case import ScheduledReportUseCase
from jira_telegram_bot.use_cases.send_deadline_alerts_use_case import (
    SendDeadlineAlertsUseCase,
)
from jira_telegram_bot.use_cases.bugs_synchronization import (
    FetchBugImprovementDataUseCase,
)
from jira_telegram_bot.use_cases.bugs_synchronization import (
    SyncBugImprovementToSheetsUseCase,
)
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase
from jira_telegram_bot.use_cases.story_synchronization import (
    FetchStoryDataUseCase,
)
from jira_telegram_bot.use_cases.story_synchronization import (
    SyncStoryToSheetsUseCase,
)
from jira_telegram_bot.use_cases.interfaces.task_story_repository_interface import (
    TaskStoryRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.team_evaluation_repository_interface import (
    TeamEvaluationRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.team_evaluation_calculation_log_repository_interface import (
    TeamEvaluationCalculationLogRepositoryInterface,
)
from jira_telegram_bot.adapters.repositories.task_story_repository import (
    TaskStoryRepository,
)

from jira_telegram_bot.use_cases.telegram_commands.get_current_stories import (
    GetCurrentStoriesUseCase,
)
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import (
    DailyTaskStatus,
)
from jira_telegram_bot.use_cases.webhooks import JiraWebhookUseCase
from jira_telegram_bot.use_cases.webhooks import TelegramWebhookUseCase
from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSyncConfig
from jira_telegram_bot.entities.story_synchronization import StorySyncConfig

def read_user_config(config_path: Path) -> Dict[str, Any]:
    """Read user configuration from specified path.

    Args:
        config_path: Path to the user configuration directory

    Returns:
        Dictionary with user configuration data
    """
    try:
        LOGGER.info(f"Reading user configuration from {config_path}")
        return {}
    except Exception as e:
        LOGGER.error(f"Error reading user configuration: {str(e)}")
        return {}


def _load_bug_improvement_sync_config() -> BugImprovementSyncConfig:
    """Load bug/improvement sync configuration.

    Returns:
        BugImprovementSyncConfig entity with board-to-sheet mappings.
    """
    import json
    from jira_telegram_bot import DEFAULT_PATH

    config_path = DEFAULT_PATH / "config" / "bug_improvement_sync_config.json"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return BugImprovementSyncConfig(**config_data)
    except Exception as e:
        LOGGER.warning(
            f"Failed to load bug improvement sync config from {config_path}: {e}",
        )
        return BugImprovementSyncConfig(mappings=[])


def _load_story_sync_config() -> StorySyncConfig:
    """Load story sync configuration.

    Returns:
        StorySyncConfig entity with board-to-sheet mappings.
    """
    import json
    from jira_telegram_bot import DEFAULT_PATH

    config_path = DEFAULT_PATH / "config" / "story_sync_config.json"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return StorySyncConfig(**config_data)
    except Exception as e:
        LOGGER.warning(
            f"Failed to load story sync config from {config_path}: {e}",
        )
        return StorySyncConfig(mappings=[])


def configure_container() -> Container:
    """Configure the dependency injection container.

    Returns:
        Configured Lagom container
    """
    container = Container()

    # Configure directories
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    config_dir = Path(os.environ.get("CONFIG_DIR", "./config"))

    # Configure settings
    _configure_settings(container)

    # Configure database connections
    _configure_database(container)

    # Configure repositories
    _configure_repositories(container, data_dir, config_dir)

    # Configure services and gateways
    _configure_services_and_gateways(container)

    # Configure AI agents and models
    _configure_ai_agents_and_models(container)

    # Configure use cases
    _configure_use_cases(container)

    # Configure API endpoints
    _configure_api_endpoints(container)

    # Configure metrics tracking
    _configure_metrics_tracking(container)

    _configure_synth_pm_board(container)

    # Configure team evaluation
    configure_team_evaluation_dependencies(container)
    
    # Configure daily task tracking
    _configure_daily_task_tracking(container)

    return container


def _configure_settings(container: Container) -> None:
    """Configure application settings."""
    container[JiraConnectionSettings] = Singleton(lambda: JiraConnectionSettings())
    container[TelegramConnectionSettings] = Singleton(
        lambda: TelegramConnectionSettings(),
    )
    container[TelegramWebhookConnectionSettings] = Singleton(
        lambda: TelegramWebhookConnectionSettings(),
    )
    container[OpenAISettings] = Singleton(lambda: OpenAISettings())
    container[GeminiConnectionSetting] = Singleton(lambda: GeminiConnectionSetting())
    container[GitlabSettings] = Singleton(lambda: GitlabSettings())
    container[PostgresSettings] = Singleton(lambda: PostgresSettings())
    container[JiraBoardSettings] = Singleton(lambda: JiraBoardSettings())
    container[GoogleSheetsConnectionSettings] = Singleton(
        lambda: GoogleSheetsConnectionSettings(),
    )
    container[FastAPISettings] = Singleton(lambda: FastAPISettings())
    container[DeadlineNotifierSettings] = Singleton(lambda: DeadlineNotifierSettings())
    container[JiraSyncSettings] = Singleton(lambda: JiraSyncSettings())


def _configure_database(container: Container) -> None:
    """Configure database connections."""
    container[DatabaseConnectionInterface] = Singleton(
        lambda c: PostgreSQLConnection(c[PostgresSettings]),
    )


def _configure_repositories(
    container: Container,
    data_dir: Path,
    config_dir: Path,
) -> None:
    """Configure repository implementations."""
    # Jira repositories
    jira_mode = os.environ.get("JIRA_MODE", "").lower()
    if jira_mode == "mock":
        from jira_telegram_bot.adapters.repositories.jira.mock_jira_repository import (
            MockJiraRepository,
        )

        container[TaskManagerRepositoryInterface] = Singleton(
            lambda: MockJiraRepository(),
        )
        LOGGER.warning("Using MOCK Jira repository for development/testing")
    else:
        container[TaskManagerRepositoryInterface] = Singleton(
            lambda c: JiraCloudRepository(c[JiraConnectionSettings])
            if c[JiraConnectionSettings].connection_type == JiraConnectionType.CLOUD
            else JiraServerRepository(c[JiraConnectionSettings]),
        )

    # File-based repositories
    container[ProjectInfoRepositoryInterface] = Singleton(
        lambda c: ProjectInfoRepository(),
    )
    container[UserAuthenticationInterface] = Singleton(
        lambda c: FileUserAuthenticationRepository(
            auth_file_path=str(config_dir / "allowed_users.json"),
        ),
    )
    container[NotificationLogRepositoryInterface] = Singleton(
        lambda c: FileNotificationLogRepository(
            log_file_path=str(data_dir / "notifier_log.jsonl"),
        ),
    )
    container[ProgressReportRepositoryInterface] = Singleton(
        lambda c: FileProgressReportRepository(
            storage_path=str(data_dir / "storage" / "progress_reports.json"),
        ),
    )
    container[JiraReportRepositoryInterface] = Singleton(
        lambda c: JiraReportRepository(c[DatabaseConnectionInterface]),
    )

    container[TeamEvaluationRepositoryInterface] = Singleton(
        lambda c: PostgresTeamEvaluationRepository(
            db_connection=c[DatabaseConnectionInterface]
        ),
    )

    container[TeamEvaluationCalculationLogRepositoryInterface] = Singleton(
        lambda c: PostgreSQLTeamEvaluationCalculationLogRepository(
            db_connection=c[DatabaseConnectionInterface]
        ),
    )


def _configure_services_and_gateways(container: Container) -> None:
    """Configure service implementations and gateways."""
    # Google Sheets
    container[GoogleSheetClient] = Singleton(
        lambda c: GoogleSheetClient(c[GoogleSheetsConnectionSettings]),
    )

    # Notification services
    container[NotificationGatewayInterface] = Singleton(
        lambda c: NotificationGateway(c[TelegramConnectionSettings]),
    )
    container[TelegramNotifierInterface] = Singleton(
        lambda c: TelegramNotifier(
            telegram_settings=c[TelegramConnectionSettings],
            user_config_repository=c[UserConfigInterface],
        ),
    )

    # User configuration
    container[UserConfigInterface] = Singleton(
        lambda c: UserConfig(
            user_config_path=str(
                Path(os.environ.get("DATA_DIR", "./data"))
                / "storage"
                / "user_config.json",
            ),
        ),
    )

    # Data services
    container[JiraDataServiceInterface] = Singleton(
        lambda c: JiraDataService(c[TaskManagerRepositoryInterface]),
    )
    container[CurrentStoriesServiceInterface] = Singleton(
        lambda c: CurrentStoriesService(
            c[GoogleSheetsConnectionSettings],
            c[GoogleSheetClient],
        ),
    )
    container[XlsxReportServiceInterface] = Singleton(
        lambda c: XlsxReportService(),
    )
    container[SchedulerServiceInterface] = Singleton(
        lambda c: APSchedulerService(),
    )

    # Application startup service
    container[ApplicationStartupService] = Singleton(
        lambda c: ApplicationStartupService(c[DatabaseConnectionInterface]),
    )


def _configure_ai_agents_and_models(container: Container) -> None:
    """Configure AI models and related services."""
    # Core AI models
    container[LLMModelInterface] = Singleton(
        lambda c: LLMModels(c[OpenAISettings], c[GeminiConnectionSetting]),
    )
    container[SpeechProcessorInterface] = Singleton(
        lambda c: SpeechProcessor(c[OpenAISettings]),
    )

    # AI services
    container[AIServiceProtocol] = Singleton(
        lambda c: LangChainAiService(c[LLMModelInterface]),
    )
    container[PromptCatalogProtocol] = Singleton(
        lambda c: FilePromptCatalog(),
    )

    container[StoryDecompositionUseCase] = Singleton(
        lambda c: StoryDecompositionUseCase(
            prompt_catalog=c[PromptCatalogProtocol],
            ai_service=c[AIServiceProtocol],
        ),
    )
    container[CreateSubtasksUseCase] = Singleton(
        lambda c: CreateSubtasksUseCase(
            prompt_catalog=c[PromptCatalogProtocol],
            ai_service=c[AIServiceProtocol],
        ),
    )
    container[BoardSummarizerUseCase] = Singleton(
        lambda c: BoardSummarizerUseCase(
            prompt_catalog=c[PromptCatalogProtocol],
            ai_service=c[AIServiceProtocol],
            task_grouper=TaskGrouper(),
        ),
    )
    container[GenerateProgressReportUseCase] = Singleton(
        lambda c: GenerateProgressReportUseCase(
            prompt_catalog=c[PromptCatalogProtocol],
            ai_service=c[AIServiceProtocol],
            repository=c[ProgressReportRepositoryInterface],
        ),
    )

    container[AgentGenerateUserStory] = Singleton(
        lambda c: AgentGenerateUserStory(
            ai_service=c[AIServiceProtocol],
            prompt_catalog=c[PromptCatalogProtocol],
        ),
    )

    container[GenerateAcceptanceCriteriaUseCase] = Singleton(
        lambda c: GenerateAcceptanceCriteriaUseCase(
            ai_service=c[AIServiceProtocol],
            prompt_catalog=c[PromptCatalogProtocol],
        ),
    )

    container[GenerateTestScenariosUseCase] = Singleton(
        lambda c: GenerateTestScenariosUseCase(
            ai_service=c[AIServiceProtocol],
            prompt_catalog=c[PromptCatalogProtocol],
        ),
    )


def _configure_use_cases(container: Container) -> None:
    """Configure use case implementations."""
    # Core use cases
    container[CreateTaskUseCase] = Singleton(
        lambda c: CreateTaskUseCase(jira_repo=c[TaskManagerRepositoryInterface]),
    )
    container[ParseJiraPromptUseCase] = Singleton(
        lambda c: ParseJiraPromptUseCase(openai_gateway=c[LLMModelInterface]),
    )
    container[HandleJiraWebhookUseCase] = Singleton(
        lambda c: HandleJiraWebhookUseCase(
            jira_settings=c[JiraConnectionSettings],
            telegram_gateway=c[NotificationGatewayInterface],
            jira_repository=c[TaskManagerRepositoryInterface],
        ),
    )

    # Webhook use cases
    container[JiraWebhookUseCase] = Singleton(
        lambda c: JiraWebhookUseCase(
            jira_settings=c[JiraConnectionSettings],
            telegram_gateway=c[NotificationGatewayInterface],
        ),
    )
    container[TelegramWebhookUseCase] = Singleton(
        lambda c: TelegramWebhookUseCase(
            create_task_use_case=c[CreateTaskUseCase],
            parse_prompt_use_case=c[ParseJiraPromptUseCase],
            task_manager_repository=c[TaskManagerRepositoryInterface],
        ),
    )

    # User story generation
    container[GenerateUserStoryUseCase] = Singleton(
        lambda c: GenerateUserStoryUseCase(
            ai_generate_user_story=c[AgentGenerateUserStory],
        ),
    )

    # Alert and notification use cases
    container[SendDeadlineAlertsUseCase] = Singleton(
        lambda c: SendDeadlineAlertsUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
            user_config_repository=c[UserConfigInterface],
            telegram_notifier=c[TelegramNotifierInterface],
            notification_log_repository=c[NotificationLogRepositoryInterface],
            calendar_repository=c[CalendarRepositoryInterface],
            deadline_notifier_settings=c[DeadlineNotifierSettings],
        ),
    )

    # Project management use cases
    container[GetProjectStatusUseCase] = Singleton(
        lambda c: GetProjectStatusUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
        ),
    )
    container[UpdateProjectTrackingUseCase] = Singleton(
        lambda c: UpdateProjectTrackingUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
            user_config=c[UserConfigInterface],
        ),
    )

    # Report generation use cases
    container[GenerateJiraReportUseCase] = Singleton(
        lambda c: GenerateJiraReportUseCase(
            jira_service=c[JiraDataServiceInterface],
            report_repository=c[JiraReportRepositoryInterface],
        ),
    )
    container[ScheduledReportUseCase] = Singleton(
        lambda c: ScheduledReportUseCase(
            report_use_case=c[GenerateJiraReportUseCase],
            scheduler_service=c[SchedulerServiceInterface],
            project_keys=c[JiraSyncSettings].sync_project_keys,
        ),
    )
    container[SyncJiraIssueUseCase] = Singleton(
        lambda c: SyncJiraIssueUseCase(
            jira_service=c[JiraDataServiceInterface],
            report_repository=c[JiraReportRepositoryInterface],
        ),
    )
    container[CalculateActualDatesUseCase] = Singleton(
        lambda c: CalculateActualDatesUseCase(
            jira_repository=c[TaskManagerRepositoryInterface],
            report_repository=c[JiraReportRepositoryInterface],
        ),
    )
    container[GetCurrentStoriesUseCase] = Singleton(
        lambda c: GetCurrentStoriesUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
            current_stories_service=c[CurrentStoriesServiceInterface],
            xlsx_report_service=c[XlsxReportServiceInterface],
        ),
    )
    
    container[FetchBugImprovementDataUseCase] = Singleton(
        lambda c: FetchBugImprovementDataUseCase(
            task_manager=c[TaskManagerRepositoryInterface],
            jira_base_url=f"{c[JiraConnectionSettings].domain.scheme}://{c[JiraConnectionSettings].domain.host}",
            user_config=c[UserConfigInterface],
        ),
    )
    
    container[SyncBugImprovementToSheetsUseCase] = Singleton(
        lambda c: SyncBugImprovementToSheetsUseCase(
            fetch_data_use_case=c[FetchBugImprovementDataUseCase],
            sheets_gateway=c[SpreadsheetGatewayInterface],
            sync_config=_load_bug_improvement_sync_config(),
            jira_base_url=f"{c[JiraConnectionSettings].domain.scheme}://{c[JiraConnectionSettings].domain.host}",
        ),
    )

    container[FetchStoryDataUseCase] = Singleton(
        lambda c: FetchStoryDataUseCase(
            task_manager=c[TaskManagerRepositoryInterface],
            jira_base_url=f"{c[JiraConnectionSettings].domain.scheme}://{c[JiraConnectionSettings].domain.host}",
            user_config=c[UserConfigInterface],
            pm_project_key=c[JiraSyncSettings].pm_project_key,
        ),
    )

    container[TaskStoryRepositoryInterface] = Singleton(
        lambda c: TaskStoryRepository(
            sheets_gateway=c[SpreadsheetGatewayInterface],
            user_config=c[UserConfigInterface],
        ),
    )

    container[SyncStoryToSheetsUseCase] = Singleton(
        lambda c: SyncStoryToSheetsUseCase(
            fetch_data_use_case=c[FetchStoryDataUseCase],
            sheets_gateway=c[SpreadsheetGatewayInterface],
            sync_config=_load_story_sync_config(),
            jira_base_url=f"{c[JiraConnectionSettings].domain.scheme}://{c[JiraConnectionSettings].domain.host}",
            user_config=c[UserConfigInterface],
            task_story_repository=c[TaskStoryRepositoryInterface],
        ),
    )


def _configure_api_endpoints(container: Container) -> None:
    """Configure API endpoint implementations."""
    container[SubServiceEndpoints] = Singleton(lambda: SubServiceEndpoints())
    container[FastAPIConfig] = Singleton(lambda: FastAPIConfig())

    # Controllers
    container[GitlabWebhookController] = Singleton(
        lambda c: GitlabWebhookController(
            process_gitlab_event_use_case=c[ProcessGitlabEventUseCase],
        ),
    )

    # Webhook endpoints
    container[JiraWebhookEndpoint] = Singleton(
        lambda c: JiraWebhookEndpoint(jira_webhook_controller=c[JiraWebhookController]),
    )
    container[TelegramWebhookEndpoint] = Singleton(
        lambda c: TelegramWebhookEndpoint(
            telegram_webhook_use_case=c[TelegramWebhookUseCase],
        ),
    )

    # System endpoints
    container[HealthCheckEndpoint] = Singleton(lambda: HealthCheckEndpoint())
    container[ProjectStatusEndpoint] = Singleton(
        lambda c: ProjectStatusEndpoint(
            get_project_status_use_case=c[GetProjectStatusUseCase],
            update_project_tracking_use_case=c[UpdateProjectTrackingUseCase],
        ),
    )


def _configure_metrics_tracking(container: Container) -> None:
    """Configure metrics tracking components."""
    # Metrics gateways and repositories
    container[SpreadsheetGatewayInterface] = Singleton(
        lambda c: GoogleSheetsGateway(c[GoogleSheetClient]),
    )
    container[UserSettingConfigurationRepositoryInterface] = Singleton(
        lambda c: FileUserSettingConfigurationRepository(),
    )

    # Metrics use cases
    container[UpdateSheetUseCase] = Singleton(
        lambda c: UpdateSheetUseCase(
            spreadsheet_gateway=c[SpreadsheetGatewayInterface],
            user_config_repository=c[UserSettingConfigurationRepositoryInterface],
        ),
    )
    container[MetricsProcessorInterface] = Singleton(
        lambda c: MetricsProcessorService(c[UpdateSheetUseCase]),
    )
    container[ProcessJiraEventUseCase] = Singleton(
        lambda c: ProcessJiraEventUseCase(c[MetricsProcessorInterface]),
    )
    container[ProcessGitlabEventUseCase] = Singleton(
        lambda c: ProcessGitlabEventUseCase(c[MetricsProcessorInterface]),
    )

    # Metrics endpoints
    container[MetricsWebhookEndpoint] = Singleton(
        lambda c: MetricsWebhookEndpoint(
            jira_webhook_controller=c[JiraWebhookController],
            gitlab_webhook_controller=c[GitlabWebhookController],
        ),
    )


def _configure_synth_pm_board(container: Container) -> None:
    """Configure SynthPM components."""
    # Import adapters
    from jira_telegram_bot.adapters.synth_pm import (
        SynthPMGoogleSheetsAdapter,
        SynthPMJiraAdapter,
    )

    # Settings
    container[SynthPMSettings] = Singleton(
        lambda: SynthPMSettings(),
    )

    # Repository
    container[SynthPMRepositoryInterface] = Singleton(
        lambda c: SynthPMRepository(
            google_sheet_client=c[GoogleSheetClient],
            jira_repository=c[TaskManagerRepositoryInterface],
            settings=c[SynthPMSettings],
            user_config=c[UserConfigInterface]
        )
    )

    # Adapters
    container["SynthPMGoogleSheetsAdapter"] = Singleton(
        lambda c: SynthPMGoogleSheetsAdapter(
            google_sheet_client=c[GoogleSheetClient],
            settings=c[SynthPMSettings],
            user_config=c[UserConfigInterface],
        ),
    )

    container["SynthPMJiraAdapter"] = Singleton(
        lambda c: SynthPMJiraAdapter(
            jira_repository=c[TaskManagerRepositoryInterface],
            settings=c[SynthPMSettings],
        ),
    )
    


    # Use case
    container[SynthPMUseCase] = Singleton(
        lambda c: SynthPMUseCase(
            repository=c[SynthPMRepositoryInterface],
            settings=c[SynthPMSettings],
            user_config=c[UserConfigInterface],
            notification_gateway=NotificationGateway(token=c[SynthPMSettings].telegram_bot_token),
            generate_acceptance_criteria_use_case=c[GenerateAcceptanceCriteriaUseCase],
            generate_test_scenarios_use_case=c[GenerateTestScenariosUseCase],
        )
    )

    # Endpoint (will be imported when needed)
    container[SynthPMEndpoint] = Singleton(
        lambda c: SynthPMEndpoint(c[SynthPMUseCase]),
    )


def configure_team_evaluation_dependencies(container: Container):
    """Configure team evaluation specific dependencies."""
    from jira_telegram_bot.settings.team_evaluation_settings import (
        TeamEvaluationSettings,
    )
    from jira_telegram_bot.adapters.repositories.calendar.api_calendar_repository import (
        ApiCalendarRepository,
    )
    from jira_telegram_bot.adapters.repositories.leave import JsonLeaveRepository
    from jira_telegram_bot.adapters.gateways.google_sheets.team_evaluation_gateway import (
        TeamEvaluationGoogleSheetGateway,
    )
    from jira_telegram_bot.adapters.controllers.jira_webhook_controller import (
        JiraWebhookController,
    )
    from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import (
        CalendarRepositoryInterface,
    )
    from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import (
        LeaveRepositoryInterface,
    )
    from jira_telegram_bot.use_cases.interfaces.google_sheet_gateway_interface import (
        GoogleSheetGatewayInterface,
    )
    from jira_telegram_bot.use_cases.team_evaluation import (
        SprintClosedTeamEvaluationUseCase,
        SprintWebhookHandler,
    )
    from jira_telegram_bot.use_cases.webhooks import JiraWebhookUseCase
    from jira_telegram_bot.use_cases.metrics.process_jira_event_use_case import (
        ProcessJiraEventUseCase,
    )

    # Settings
    container[TeamEvaluationSettings] = Singleton(
        lambda: TeamEvaluationSettings(),
    )

    # Repositories - Using API-based calendar repository
    container[CalendarRepositoryInterface] = Singleton(
        lambda: ApiCalendarRepository(base_url="https://holidayapi.ir/jalali"),
    )

    container[LeaveRepositoryInterface] = Singleton(
        lambda: JsonLeaveRepository(),
    )

    # Gateways
    container[GoogleSheetGatewayInterface] = Singleton(
        lambda c: TeamEvaluationGoogleSheetGateway(
            google_sheet_client=c[GoogleSheetClient],
        ),
    )

    # Use cases
    container[SprintClosedTeamEvaluationUseCase] = Singleton(
        lambda c: SprintClosedTeamEvaluationUseCase(
            task_manager_repo=c[TaskManagerRepositoryInterface],
            user_config_service=c[UserConfigInterface],
            google_sheet_gateway=c[GoogleSheetGatewayInterface],
            calendar_repo=c[CalendarRepositoryInterface],
            leave_repo=c[LeaveRepositoryInterface],
            team_evaluation_repo=c[TeamEvaluationRepositoryInterface],
            calculation_log_repo=c[TeamEvaluationCalculationLogRepositoryInterface],
            settings=c[TeamEvaluationSettings],
        ),
    )

    container[SprintWebhookHandler] = Singleton(
        lambda c: SprintWebhookHandler(
            team_evaluation_use_case=c[SprintClosedTeamEvaluationUseCase],
        ),
    )

    # Daily task status use case
    container[DailyTaskStatus] = Singleton(
        lambda c: DailyTaskStatus(
            jira_repository=c[TaskManagerRepositoryInterface],
            user_config=c[UserConfigInterface],
        ),
    )

    # Override JiraWebhookController to include sprint handler
    container[JiraWebhookController] = Singleton(
        lambda c: JiraWebhookController(
            jira_webhook_use_case=c[JiraWebhookUseCase],
            process_jira_event_use_case=c[ProcessJiraEventUseCase],
            sprint_webhook_handler=c[SprintWebhookHandler],
        ),
    )


def _configure_daily_task_tracking(container: Container):
    """Configure daily task tracking dependencies."""
    from jira_telegram_bot.settings.daily_task_tracker_settings import (
        DailyTaskTrackerSettings,
    )
    from jira_telegram_bot.adapters.repositories.file_storage.file_daily_task_tracking_repository import (
        FileDailyTaskTrackingRepository,
    )
    from jira_telegram_bot.use_cases.interfaces.daily_task_tracking_repository_interface import (
        DailyTaskTrackingRepositoryInterface,
    )
    from jira_telegram_bot.use_cases.daily_task_tracking import (
        GetUserDailyTasksUseCase,
        ValidateWorklogUseCase,
        DetectStatusRegressionUseCase,
        RecordDelayReasonUseCase,
        RecordTimeSpentUseCase,
        RecordWorklogUseCase,
        RequestSubtaskCreationUseCase,
        ParseWorklogReportUseCase,
        ConfirmWorklogReportUseCase,
    )
    from jira_telegram_bot.use_cases.daily_task_tracking.send_daily_task_reminders_use_case import (
        SendDailyTaskRemindersUseCase,
    )
    from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
        DailyTaskTrackingHandler,
    )
    from jira_telegram_bot.frameworks.telegram.daily_task_queue_manager import (
        DailyTaskQueueManager,
    )
    from jira_telegram_bot.frameworks.scheduler.daily_task_tracker_job import (
        DailyTaskTrackerJob,
    )

    container[DailyTaskTrackerSettings] = Singleton(
        lambda: DailyTaskTrackerSettings()
    )

    container[DailyTaskTrackingRepositoryInterface] = Singleton(
        lambda c: FileDailyTaskTrackingRepository(
            storage_path="data/storage/daily_task_tracking.jsonl",
        )
    )

    container[GetUserDailyTasksUseCase] = Singleton(
        lambda c: GetUserDailyTasksUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
        )
    )

    container[ValidateWorklogUseCase] = Singleton(
        lambda c: ValidateWorklogUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
        )
    )

    container[DetectStatusRegressionUseCase] = Singleton(
        lambda c: DetectStatusRegressionUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
        )
    )

    container[RecordDelayReasonUseCase] = Singleton(
        lambda c: RecordDelayReasonUseCase(
            tracking_repository=c[DailyTaskTrackingRepositoryInterface],
        )
    )

    container[RecordTimeSpentUseCase] = Singleton(
        lambda c: RecordTimeSpentUseCase(
            tracking_repository=c[DailyTaskTrackingRepositoryInterface],
        )
    )

    container[RecordWorklogUseCase] = Singleton(
        lambda c: RecordWorklogUseCase(
            task_manager_repository=c[TaskManagerRepositoryInterface],
            tracking_repository=c[DailyTaskTrackingRepositoryInterface],
        )
    )

    container[RequestSubtaskCreationUseCase] = Singleton(
        lambda c: RequestSubtaskCreationUseCase(
            tracking_repository=c[DailyTaskTrackingRepositoryInterface],
            project_info_repository=c[ProjectInfoRepositoryInterface],
            user_config_repository=c[UserConfigInterface],
            telegram_notifier=c[TelegramNotifierInterface],
        )
    )

    container[DailyTaskQueueManager] = Singleton(
        lambda c: DailyTaskQueueManager()
    )

    container[ParseWorklogReportUseCase] = Singleton(
        lambda c: ParseWorklogReportUseCase(
            ai_service=c[AIServiceProtocol],
            prompt_catalog=c[PromptCatalogProtocol],
        )
    )

    container[ConfirmWorklogReportUseCase] = Singleton(
        lambda c: ConfirmWorklogReportUseCase()
    )

    container[DailyTaskTrackingHandler] = Singleton(
        lambda c: DailyTaskTrackingHandler(
            record_delay_reason_use_case=c[RecordDelayReasonUseCase],
            record_time_spent_use_case=c[RecordTimeSpentUseCase],
            record_worklog_use_case=c[RecordWorklogUseCase],
            request_subtask_creation_use_case=c[RequestSubtaskCreationUseCase],
            user_config_repository=c[UserConfigInterface],
            queue_manager=c[DailyTaskQueueManager],
        )
    )

    container[SendDailyTaskRemindersUseCase] = Singleton(
        lambda c: SendDailyTaskRemindersUseCase(
            get_user_daily_tasks_use_case=c[GetUserDailyTasksUseCase],
            detect_status_regression_use_case=c[DetectStatusRegressionUseCase],
            user_config_repository=c[UserConfigInterface],
            telegram_notifier=c[TelegramNotifierInterface],
            task_manager_repository=c[TaskManagerRepositoryInterface],
            project_info_repository=c[ProjectInfoRepositoryInterface],
            daily_task_tracking_handler=c[DailyTaskTrackingHandler],
            telegram_token=c[TelegramConnectionSettings].HOOK_TOKEN,
            queue_manager=c[DailyTaskQueueManager],
        )
    )

    container[DailyTaskTrackerJob] = Singleton(
        lambda c: DailyTaskTrackerJob(
            send_daily_task_reminders_use_case=c[SendDailyTaskRemindersUseCase],
            settings=c[DailyTaskTrackerSettings],
            scheduler_service=c[SchedulerServiceInterface],
        )
    )
