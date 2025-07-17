"""File-based user setting configuration repository."""

import json
import os
from typing import Optional, Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.metrics.constants import SheetName
from jira_telegram_bot.use_cases.interfaces.metrics.user_setting_configuration_repository_interface import UserSettingConfigurationRepositoryInterface


class FileUserSettingConfigurationRepository(UserSettingConfigurationRepositoryInterface):
    """File-based implementation of user configuration repository for metrics."""
    
    def __init__(self, config_file_path: str = "data/metrics_config.json"):
        """Initialize the repository.
        
        Args:
            config_file_path: Path to the configuration file
        """
        self.config_file_path = config_file_path
        self._config_cache: Optional[Dict[str, Any]] = None
    
    async def get_developer_sheet_mapping(self, jira_username: str) -> Optional[Dict[str, Any]]:
        """Get sheet mapping configuration for a developer.
        
        Args:
            jira_username: Jira username of the developer
            
        Returns:
            Dictionary containing sheet mapping info or None if not found
        """
        config = await self._load_config()
        
        developers = config.get("developers", {})
        developer_config = developers.get(jira_username)
        
        if developer_config:
            LOGGER.debug(f"Found developer mapping for {jira_username}")
            return developer_config
        
        # Try to find by email if not found by username
        for username, dev_config in developers.items():
            if dev_config.get("email") == jira_username:
                LOGGER.debug(f"Found developer mapping for {jira_username} by email")
                return dev_config
        
        LOGGER.warning(f"No developer mapping found for {jira_username}")
        return None
    
    async def get_sheet_configuration(self, sheet_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific sheet.
        
        Args:
            sheet_name: Name of the sheet (from SheetName enum)
            
        Returns:
            Dictionary containing sheet config or None if not found
        """
        config = await self._load_config()
        
        sheets = config.get("sheets", {})
        sheet_config = sheets.get(sheet_name)
        
        if sheet_config:
            LOGGER.debug(f"Found sheet configuration for {sheet_name}")
            return sheet_config
        
        LOGGER.warning(f"No sheet configuration found for {sheet_name}")
        return None
    
    async def get_project_sheet_mapping(self, project_key: str) -> Optional[str]:
        """Get sheet ID for a specific project.
        
        Args:
            project_key: Jira project key
            
        Returns:
            Sheet ID for the project or None if not found
        """
        config = await self._load_config()
        
        projects = config.get("projects", {})
        project_config = projects.get(project_key)
        
        if project_config and "sheet_id" in project_config:
            LOGGER.debug(f"Found sheet mapping for project {project_key}")
            return project_config["sheet_id"]
        
        # Fallback to default sheet
        default_sheet = config.get("default_sheet_id")
        if default_sheet:
            LOGGER.debug(f"Using default sheet for project {project_key}")
            return default_sheet
        
        LOGGER.warning(f"No sheet mapping found for project {project_key}")
        return None
    
    async def get_sprint_sheet_mapping(self, sprint_id: str) -> Optional[str]:
        """Get sheet ID for a specific sprint.
        
        Args:
            sprint_id: Sprint identifier
            
        Returns:
            Sheet ID for the sprint or None if not found
        """
        config = await self._load_config()
        
        sprints = config.get("sprints", {})
        sprint_config = sprints.get(sprint_id)
        
        if sprint_config and "sheet_id" in sprint_config:
            LOGGER.debug(f"Found sheet mapping for sprint {sprint_id}")
            return sprint_config["sheet_id"]
        
        # Fallback to default sheet
        default_sheet = config.get("default_sheet_id")
        if default_sheet:
            LOGGER.debug(f"Using default sheet for sprint {sprint_id}")
            return default_sheet
        
        LOGGER.warning(f"No sheet mapping found for sprint {sprint_id}")
        return None
    
    async def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file with caching.
        
        Returns:
            Configuration dictionary
        """
        if self._config_cache is not None:
            return self._config_cache
        
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as file:
                    config = json.load(file)
                    self._config_cache = config
                    LOGGER.debug(f"Loaded metrics configuration from {self.config_file_path}")
                    return config
            else:
                LOGGER.warning(f"Configuration file not found: {self.config_file_path}")
                # Return default configuration
                default_config = self._get_default_config()
                await self._save_config(default_config)
                return default_config
                
        except Exception as e:
            LOGGER.error(f"Error loading configuration from {self.config_file_path}: {e}")
            return self._get_default_config()
    
    async def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            
            with open(self.config_file_path, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
            
            self._config_cache = config
            LOGGER.info(f"Saved metrics configuration to {self.config_file_path}")
            
        except Exception as e:
            LOGGER.error(f"Error saving configuration to {self.config_file_path}: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "default_sheet_id": "your_default_google_sheet_id",
            "sheets": {
                SheetName.DAILY_SCOREBOARD: {
                    "sheet_id": "your_daily_scoreboard_sheet_id",
                    "range_template": "Daily!A:G",
                    "column_mappings": {
                        "developer_name": 0,
                        "date": 1,
                        "today_deadlines": 2,
                        "resolved_tasks": 3,
                        "logged_time": 4,
                        "commits": 5,
                        "comments": 6
                    }
                },
                SheetName.DEVELOPER_METRICS_MATRIX: {
                    "sheet_id": "your_sprint_matrix_sheet_id", 
                    "range_template": "Sprint!A:P",
                    "column_mappings": {
                        "developer_name": 0,
                        "all_tasks": 1,
                        "completed_tasks": 2,
                        "releases_related_to_person": 3,
                        "stories_related_to_person": 4,
                        "resolved_stories": 5,
                        "resolved_bugs": 6,
                        "delivery_delay_by_day": 7,
                        "bug_delivery_delay_by_day": 8,
                        "logged_time": 9,
                        "eta_completing_all_tasks": 10,
                        "logged_time_support_epic": 11,
                        "logged_meeting": 12,
                        "documentatio_merge_requests": 13,
                        "merge_requests": 14,
                        "successful_merges": 15
                    }
                }
            },
            "developers": {
                "john.doe@example.com": {
                    "display_name": "John Doe",
                    "email": "john.doe@example.com",
                    "jira_username": "john.doe",
                    "gitlab_username": "jdoe",
                    "sheet_row": 2
                },
                "jane.smith@example.com": {
                    "display_name": "Jane Smith", 
                    "email": "jane.smith@example.com",
                    "jira_username": "jane.smith",
                    "gitlab_username": "jsmith",
                    "sheet_row": 3
                }
            },
            "projects": {
                "EXAMPLE": {
                    "sheet_id": "project_specific_sheet_id",
                    "name": "Example Project"
                }
            },
            "sprints": {
                "123": {
                    "sheet_id": "sprint_specific_sheet_id",
                    "name": "Sprint 123"
                }
            }
        }
    
    def invalidate_cache(self) -> None:
        """Invalidate the configuration cache to force reload."""
        self._config_cache = None
        LOGGER.debug("Invalidated metrics configuration cache")
