"""Multi-project synchronization service for SynthPM."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.synth_pm.project_config import ProjectConfig
from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import APSchedulerService
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


class SynthPMMultiProjectSyncService:
    """Service for managing multi-project synchronization using APScheduler."""

    def __init__(
        self,
        settings: SynthPMSettings,
        scheduler: Optional[APSchedulerService] = None,
        project_keys: Optional[List[str]] = None,
    ):
        """Initialize the multi-project sync service.

        Args:
            settings: SynthPM settings
            scheduler: Optional APScheduler service (will be created if not provided)
            project_keys: Optional list of project keys to sync (None = all projects)
        """
        self.settings = settings
        self.project_keys = project_keys
        self.scheduler = scheduler or APSchedulerService()
        self.use_cases: Dict[str, SynthPMUseCase] = {}

    async def initialize(self):
        """Initialize use cases for all projects."""
        multi_config = self.settings.load_multi_project_config()
        
        # Determine which projects to sync
        if self.project_keys:
            projects = [p for p in multi_config.projects if p.project_key in self.project_keys]
        else:
            projects = multi_config.projects
        
        if not projects:
            LOGGER.warning("No projects configured for synchronization")
            return
        
        # Create use case instance for each project
        container = get_container()
        
        for project in projects:
            if not project.boards.developer_board.enabled:
                LOGGER.info(f"Skipping disabled project: {project.project_key}")
                continue
            
            try:
                # Import here to avoid circular dependencies
                from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
                from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
                    SynthPMRepository,
                )
                from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
                    TaskManagerRepositoryInterface,
                )
                from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
                    UserConfigInterface,
                )
                from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
                    NotificationGatewayInterface,
                )
                from jira_telegram_bot.use_cases.ai_agents.generate_acceptance_criteria import (
                    GenerateAcceptanceCriteriaUseCase,
                )
                from jira_telegram_bot.use_cases.ai_agents.generate_test_scenarios import (
                    GenerateTestScenariosUseCase,
                )
                
                # Create project-specific repository
                repository = SynthPMRepository(
                    google_sheet_client=container[GoogleSheetClient],
                    jira_repository=container[TaskManagerRepositoryInterface],
                    settings=self.settings,
                    user_config=container[UserConfigInterface],
                    project_key=project.project_key,
                )
                
                # Create use case
                use_case = SynthPMUseCase(
                    repository=repository,
                    settings=self.settings,
                    user_config=container[UserConfigInterface],
                    notification_gateway=container[NotificationGatewayInterface],
                    generate_acceptance_criteria_use_case=container[
                        GenerateAcceptanceCriteriaUseCase
                    ],
                    generate_test_scenarios_use_case=container[GenerateTestScenariosUseCase],
                )
                
                self.use_cases[project.project_key] = use_case
                LOGGER.info(
                    f"Initialized SynthPM sync for project: {project.project_key} "
                    f"(interval: {project.sync_settings.sync_interval_minutes} minutes)"
                )
                
            except Exception as e:
                LOGGER.error(f"Failed to initialize project {project.project_key}: {e}", exc_info=True)

    async def start(self):
        """Start synchronization for all projects using APScheduler."""
        if not self.use_cases:
            await self.initialize()
        
        if not self.use_cases:
            LOGGER.error("No projects initialized for synchronization")
            return
        
        # Schedule each project's sync job
        for project_key, use_case in self.use_cases.items():
            project_config = use_case.repository.project_config
            sync_interval_minutes = project_config.sync_settings.sync_interval_minutes
            
            # Create async wrapper for the sync job with proper closure
            def create_sync_job(pk: str, uc: SynthPMUseCase, pc: ProjectConfig):
                async def sync_job():
                    await self._execute_project_sync(pk, uc, pc)
                return sync_job
            
            # Schedule the job
            await self.scheduler.schedule_recurring_job(
                job_func=create_sync_job(project_key, use_case, project_config),
                interval_minutes=sync_interval_minutes,
                job_name=f"synth_pm_sync_{project_key}",
            )
        
        # Start the scheduler
        LOGGER.info(
            f"Starting APScheduler for {len(self.use_cases)} project(s): "
            f"{', '.join(self.use_cases.keys())}"
        )
        await self.scheduler.start_scheduler()

    async def stop(self):
        """Stop all synchronization tasks."""
        LOGGER.info("Stopping multi-project SynthPM sync service...")
        await self.scheduler.stop_scheduler()
        LOGGER.info("Stopped all multi-project SynthPM sync tasks")

    async def _execute_project_sync(
        self,
        project_key: str,
        use_case: SynthPMUseCase,
        project_config: ProjectConfig,
    ):
        """Execute sync for a single project.

        Args:
            project_key: Project key
            use_case: Project-specific use case
            project_config: Project configuration
        """
        try:
            LOGGER.info(f"[{project_key}] Starting sync cycle")
            
            # Sync features
            result = await use_case.sync_developer_board_features()
            
            if result["status"] == "success":
                results = result.get("results", {})
                LOGGER.info(
                    f"[{project_key}] Sync completed - "
                    f"Created: {results.get('created_jira_tasks', 0)} PM, "
                    f"{results.get('created_developer_board_tasks', 0)} dev | "
                    f"Updated: {results.get('updated_jira_tasks', 0)} PM, "
                    f"{results.get('updated_developer_board_tasks', 0)} dev | "
                    f"Skipped: {len(results.get('skipped', []))} | "
                    f"Errors: {len(results.get('errors', []))}"
                )
            else:
                LOGGER.error(f"[{project_key}] Sync failed: {result.get('message')}")
            
            # Sync release notes if PM board is enabled
            if project_config.boards.pm_board and project_config.boards.pm_board.enabled:
                try:
                    release_result = await use_case.sync_release_notes()
                    if release_result["status"] == "success":
                        LOGGER.info(
                            f"[{project_key}] Release notes sync completed: "
                            f"{release_result.get('results', {})}"
                        )
                except Exception as e:
                    LOGGER.error(f"[{project_key}] Release notes sync error: {e}")
                    
        except Exception as e:
            LOGGER.error(
                f"[{project_key}] Error in sync execution: {e}",
                exc_info=True,
            )

    async def trigger_sync(self, project_key: Optional[str] = None) -> Dict[str, dict]:
        """Manually trigger sync for one or all projects.

        Args:
            project_key: Optional project key (None = all projects)

        Returns:
            Dictionary of sync results by project key
        """
        results = {}
        
        if project_key:
            # Sync specific project
            if project_key not in self.use_cases:
                return {
                    project_key: {
                        "status": "error",
                        "message": f"Project {project_key} not found or not initialized",
                    }
                }
            
            try:
                LOGGER.info(f"Manually triggering sync for project: {project_key}")
                result = await self.use_cases[project_key].sync_developer_board_features()
                results[project_key] = result
            except Exception as e:
                results[project_key] = {
                    "status": "error",
                    "message": str(e),
                }
        else:
            # Sync all projects
            for pk, use_case in self.use_cases.items():
                try:
                    LOGGER.info(f"Manually triggering sync for project: {pk}")
                    result = await use_case.sync_developer_board_features()
                    results[pk] = result
                except Exception as e:
                    results[pk] = {
                        "status": "error",
                        "message": str(e),
                    }
        
        return results

    def get_status(self) -> Dict[str, dict]:
        """Get status of all project sync tasks.

        Returns:
            Status information for each project
        """
        status = {
            "running": self.scheduler._is_running,
            "projects": {},
        }
        
        for project_key, use_case in self.use_cases.items():
            project_config = use_case.repository.project_config
            
            status["projects"][project_key] = {
                "enabled": project_config.boards.developer_board.enabled,
                "sync_interval_minutes": project_config.sync_settings.sync_interval_minutes,
                "scheduled": self.scheduler._is_running,
                "pm_board_enabled": (
                    project_config.boards.pm_board.enabled
                    if project_config.boards.pm_board
                    else False
                ),
            }
        
        return status
