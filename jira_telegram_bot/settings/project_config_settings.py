"""Settings for project configuration management."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.entities.synth_pm.project_config import ProjectConfig
from jira_telegram_bot.entities.synth_pm.project_config import ProjectsConfig


class ProjectConfigSettings(BaseSettings):
    """Settings for loading and managing project configurations."""
    
    config_file_path: str = Field(
        default="config/projects_config.json",
        description="Path to projects configuration JSON file",
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="projects_config_",
        extra="ignore",
    )
    
    def load_config(self) -> ProjectsConfig:
        """Load projects configuration from JSON file.
        
        Returns:
            ProjectsConfig entity
            
        Raises:
            FileNotFoundError: If config file not found
            ValueError: If config file is invalid
        """
        config_path = Path(self.config_file_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return ProjectsConfig(**config_data)
    
    def get_project_config(self, project_name: str) -> Optional[ProjectConfig]:
        """Get configuration for a specific project.
        
        Args:
            project_name: Project name
            
        Returns:
            ProjectConfig if found, None otherwise
        """
        projects_config = self.load_config()
        return projects_config.get_project(project_name)
    
    def get_project_by_board_key(self, board_key: str) -> Optional[ProjectConfig]:
        """Get project configuration by Jira board key.
        
        Args:
            board_key: Jira board key
            
        Returns:
            ProjectConfig if found, None otherwise
        """
        projects_config = self.load_config()
        return projects_config.get_project_by_board_key(board_key)
    
    def get_project_by_spreadsheet_id(
        self,
        spreadsheet_id: str,
    ) -> Optional[ProjectConfig]:
        """Get project configuration by spreadsheet ID.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            
        Returns:
            ProjectConfig if found, None otherwise
        """
        projects_config = self.load_config()
        return projects_config.get_project_by_spreadsheet_id(spreadsheet_id)
