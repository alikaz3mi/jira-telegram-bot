"""Entities for modular project configuration structure."""
from __future__ import annotations

from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class GoogleSheetsTasksConfig(BaseModel):
    """Configuration for Google Sheets tasks/features sheet."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(description="Sheet name (e.g., 'ParsChat Features')")
    gid: int = Field(description="Sheet GID for URL generation")
    data_range: str = Field(description="Data range to read (e.g., 'A2:AW')")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class GoogleSheetsReleasesConfig(BaseModel):
    """Configuration for Google Sheets releases/release notes sheet."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(description="Release notes sheet name")
    gid: int = Field(description="Sheet GID for URL generation")
    data_range: str = Field(description="Release notes data range")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class GoogleSheetsConfig(BaseModel):
    """Configuration for all Google Sheets in a project."""
    
    spreadsheet_id: str = Field(description="Main spreadsheet ID")
    tasks: GoogleSheetsTasksConfig = Field(description="Tasks/Features sheet config")
    releases: GoogleSheetsReleasesConfig = Field(description="Releases sheet config")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class GoogleDocsConfig(BaseModel):
    """Configuration for Google Docs documentation."""
    
    document_id: str = Field(description="Google Docs document ID")
    document_url: str = Field(description="Google Docs document URL")
    epic_tab_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of Epic names to tab IDs",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class JiraBoardConfig(BaseModel):
    """Configuration for a single Jira board."""
    
    board_key: str = Field(description="Jira board/project key")
    board_id: Optional[int] = Field(default=None, description="Jira board ID")
    enabled: bool = Field(default=True, description="Whether this board is enabled")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class JiraConfig(BaseModel):
    """Configuration for all Jira boards in a project."""
    
    pm_board: JiraBoardConfig = Field(description="PM/Product board configuration")
    development_board: JiraBoardConfig = Field(
        description="Development board configuration",
    )
    support_board: Optional[JiraBoardConfig] = Field(
        default=None,
        description="Support board configuration (optional)",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class ProjectConfig(BaseModel):
    """Complete configuration for a single project."""
    
    project_name: str = Field(description="Project name")
    google_sheets: GoogleSheetsConfig = Field(description="Google Sheets configuration")
    google_docs: GoogleDocsConfig = Field(description="Google Docs configuration")
    jira: JiraConfig = Field(description="Jira configuration")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class ProjectsConfig(BaseModel):
    """Configuration for all projects."""
    
    projects: Dict[str, ProjectConfig] = Field(
        description="Dictionary of project configurations keyed by project name",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True
    
    def get_project(self, project_name: str) -> Optional[ProjectConfig]:
        """Get project configuration by name.
        
        Args:
            project_name: Project name
            
        Returns:
            ProjectConfig if found, None otherwise
        """
        return self.projects.get(project_name)
    
    def get_project_by_board_key(self, board_key: str) -> Optional[ProjectConfig]:
        """Get project configuration by Jira board key.
        
        Args:
            board_key: Jira board key
            
        Returns:
            ProjectConfig if found, None otherwise
        """
        for project in self.projects.values():
            if (project.jira.pm_board.board_key == board_key or
                project.jira.development_board.board_key == board_key or
                (project.jira.support_board and 
                 project.jira.support_board.board_key == board_key)):
                return project
        return None
    
    def get_project_by_spreadsheet_id(
        self,
        spreadsheet_id: str,
    ) -> Optional[ProjectConfig]:
        """Get project configuration by Google Sheets spreadsheet ID.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            
        Returns:
            ProjectConfig if found, None otherwise
        """
        for project in self.projects.values():
            if project.google_sheets.spreadsheet_id == spreadsheet_id:
                return project
        return None
