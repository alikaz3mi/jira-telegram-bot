"""CLI wrapper use case for team evaluation."""

from typing import List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.team_evaluation import SprintClosedEvent, TeamEvaluationRow
from jira_telegram_bot.settings.team_evaluation_settings import TeamEvaluationSettings
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.google_sheet_gateway_interface import GoogleSheetGatewayInterface
from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import LeaveRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface
from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import SprintClosedTeamEvaluationUseCase


class RunTeamEvaluationCliUseCase:
    """Use case for running team evaluation from CLI."""

    def __init__(
        self,
        task_manager_repo: TaskManagerRepositoryInterface,
        user_config_service: UserConfigInterface,
        google_sheet_gateway: GoogleSheetGatewayInterface,
        calendar_repo: CalendarRepositoryInterface,
        leave_repo: LeaveRepositoryInterface,
        settings: TeamEvaluationSettings
    ):
        """Initialize the CLI use case.
        
        Args:
            task_manager_repo: Task manager repository interface
            user_config_service: User configuration service
            google_sheet_gateway: Google Sheets gateway
            calendar_repo: Calendar repository
            leave_repo: Leave repository
            settings: Team evaluation settings
        """
        self.task_manager_repo = task_manager_repo
        self.user_config_service = user_config_service
        self.google_sheet_gateway = google_sheet_gateway
        self.calendar_repo = calendar_repo
        self.leave_repo = leave_repo
        self.settings = settings
        
        self.core_use_case = SprintClosedTeamEvaluationUseCase(
            task_manager_repo=task_manager_repo,
            user_config_service=user_config_service,
            google_sheet_gateway=google_sheet_gateway,
            calendar_repo=calendar_repo,
            leave_repo=leave_repo,
            settings=settings
        )

    async def run(
        self,
        sprint_id: Optional[int],
        sprint_name: Optional[str],
        project_keys: List[str]
    ) -> List[TeamEvaluationRow]:
        """Run team evaluation for CLI.
        
        Args:
            sprint_id: Jira sprint ID (optional if sprint_name provided)
            sprint_name: Sprint name (optional if sprint_id provided)
            project_keys: List of project keys to evaluate
            
        Returns:
            List of computed team evaluation rows
            
        Raises:
            ValueError: If neither sprint_id nor sprint_name provided
        """
        if not sprint_id and not sprint_name:
            raise ValueError("Either sprint_id or sprint_name must be provided")

        LOGGER.info(f"🔍 Starting team evaluation for sprint: {sprint_name or sprint_id}")
        LOGGER.info(f"📋 Projects: {', '.join(project_keys)}")

        # If we have sprint_name but no sprint_id, resolve it
        resolved_sprint_id = sprint_id
        if not resolved_sprint_id and sprint_name:
            # This would need to be implemented in the task manager repo
            # For now, we'll use a placeholder approach
            LOGGER.warning("⚠️  Sprint name resolution not yet implemented, using placeholder ID")
            resolved_sprint_id = 0

        sprint_event = SprintClosedEvent(
            sprint_id=resolved_sprint_id,
            sprint_name=sprint_name or f"Sprint {resolved_sprint_id}",
            project_keys=project_keys,
        )

        # Process via core use case
        await self.core_use_case.process_sprint_closed(sprint_event)

        LOGGER.info("✅ Team evaluation completed successfully")
        
        # Return empty list for now (core use case doesn't return rows yet)
        return []
