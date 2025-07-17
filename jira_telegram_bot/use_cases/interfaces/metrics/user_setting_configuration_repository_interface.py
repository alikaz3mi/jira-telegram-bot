"""User setting configuration repository interface."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class UserSettingConfigurationRepositoryInterface(ABC):
    """Interface for user configuration related to metrics tracking."""
    
    @abstractmethod
    async def get_developer_sheet_mapping(self, jira_username: str) -> Optional[Dict[str, Any]]:
        """Get sheet mapping configuration for a developer.
        
        Args:
            jira_username: Jira username of the developer
            
        Returns:
            Dictionary containing sheet mapping info or None if not found
            Keys include: display_name, sheet_row, gitlab_username, etc.
        """
        pass
    
    @abstractmethod
    async def get_sheet_configuration(self, sheet_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific sheet.
        
        Args:
            sheet_name: Name of the sheet (from SheetName enum)
            
        Returns:
            Dictionary containing sheet config or None if not found
            Keys include: sheet_id, range_template, column_mappings, etc.
        """
        pass
    
    @abstractmethod
    async def get_project_sheet_mapping(self, project_key: str) -> Optional[str]:
        """Get sheet ID for a specific project.
        
        Args:
            project_key: Jira project key
            
        Returns:
            Sheet ID for the project or None if not found
        """
        pass
    
    @abstractmethod
    async def get_sprint_sheet_mapping(self, sprint_id: str) -> Optional[str]:
        """Get sheet ID for a specific sprint.
        
        Args:
            sprint_id: Sprint identifier
            
        Returns:
            Sheet ID for the sprint or None if not found
        """
        pass
