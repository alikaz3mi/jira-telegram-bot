"""Use case for managing project tracking settings."""

from __future__ import annotations

from typing import Dict, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.project_tracking_interface import ProjectTrackingInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface


class UpdateProjectTrackingUseCase(ProjectTrackingInterface):
    """Use case for managing project tracking settings."""
    
    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface
    ):
        """Initialize the use case.
        
        Args:
            task_manager_repository: Repository for task management operations
            user_config: User configuration repository
        """
        self.task_manager_repository = task_manager_repository
        self.user_config = user_config
    
    async def update_tracking(
        self, 
        project_key: str,
        track: bool,
        notification_channel: Optional[str] = None
    ) -> Dict:
        """Update tracking settings for a project.
        
        Args:
            project_key: Project key
            track: Whether to track this project
            notification_channel: Optional channel ID for notifications
            
        Returns:
            Dictionary with updated tracking settings
        """
        try:
            # Validate project key
            project = await self.task_manager_repository.get_project(project_key)
            if not project:
                raise ValueError(f"Project {project_key} not found")
            
            # Update tracking settings in user config
            tracking_config = {
                "tracking_enabled": track
            }
            
            if notification_channel:
                tracking_config["notification_channel"] = notification_channel
            
            # Store in user config
            self.user_config.set_value(
                f"project_tracking.{project_key}",
                tracking_config
            )
            self.user_config.save_config()
            
            return {
                "project_key": project_key,
                "tracking_enabled": track,
                "notification_channel": notification_channel
            }
        
        except Exception as e:
            LOGGER.error(f"Error updating project tracking: {str(e)}", exc_info=True)
            raise
    
    async def get_tracking_status(self, project_key: str) -> Dict:
        """Get tracking status for a project.
        
        Args:
            project_key: Project key
            
        Returns:
            Dictionary with tracking settings
        """
        try:
            # Get tracking settings from user config
            tracking_config = self.user_config.get_value(
                f"project_tracking.{project_key}", 
                default={"tracking_enabled": False}
            )
            
            return {
                "project_key": project_key,
                "tracking_enabled": tracking_config.get("tracking_enabled", False),
                "notification_channel": tracking_config.get("notification_channel")
            }
        except Exception as e:
            LOGGER.error(f"Error getting project tracking status: {str(e)}", exc_info=True)
            return {
                "project_key": project_key,
                "tracking_enabled": False,
                "notification_channel": None
            }
