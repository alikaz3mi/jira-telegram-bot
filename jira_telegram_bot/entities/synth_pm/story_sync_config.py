"""Entities for story synchronization configuration."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class StorySyncMapping(BaseModel):
    """Mapping configuration for a single project synchronization."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(description="Sheet name (e.g., 'ParsChat Features')")
    board_key: str = Field(description="Jira board key (e.g., 'PARSCHAT')")
    gid: int = Field(description="Sheet GID for URL generation")
    data_range: str = Field(description="Data range to read (e.g., 'A2:AW')")
    
    # Google Docs configuration
    google_docs_id: Optional[str] = Field(
        default=None,
        description="Google Docs document ID for documentation",
    )
    google_docs_url: Optional[str] = Field(
        default=None,
        description="Google Docs document URL",
    )
    
    # Epic to tab mapping
    epic_tab_mappings: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Mapping of Epic names to Google Docs tab IDs",
    )
    
    # Release notes sheet configuration
    release_notes_sheet_name: Optional[str] = Field(
        default=None,
        description="Release notes sheet name in the same spreadsheet",
    )
    release_notes_data_range: Optional[str] = Field(
        default=None,
        description="Release notes data range",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class StorySyncConfig(BaseModel):
    """Complete story synchronization configuration."""
    
    mappings: List[StorySyncMapping] = Field(
        description="List of project synchronization mappings",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True
    
    def get_mapping_by_board_key(self, board_key: str) -> Optional[StorySyncMapping]:
        """Get mapping configuration by board key.
        
        Args:
            board_key: Jira board key
            
        Returns:
            StorySyncMapping if found, None otherwise
        """
        for mapping in self.mappings:
            if mapping.board_key == board_key:
                return mapping
        return None
    
    def get_mapping_by_spreadsheet_id(
        self,
        spreadsheet_id: str,
    ) -> Optional[StorySyncMapping]:
        """Get mapping configuration by spreadsheet ID.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            
        Returns:
            StorySyncMapping if found, None otherwise
        """
        for mapping in self.mappings:
            if mapping.spreadsheet_id == spreadsheet_id:
                return mapping
        return None
