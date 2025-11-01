"""Interface for Google Docs operations."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentFormatting,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import EpicTab
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureDocumentation,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    GoogleDocsStructure,
)


class GoogleDocsRepositoryInterface(ABC):
    """Interface for Google Docs repository operations."""
    
    @abstractmethod
    async def get_or_create_epic_tab(
        self,
        document_id: str,
        epic_name: str,
    ) -> str:
        """Get existing or create new Epic tab in Google Docs.
        
        Args:
            document_id: Google Docs document ID
            epic_name: Epic name for the tab
            
        Returns:
            Tab ID
            
        Raises:
            Exception: If tab creation fails
        """
        pass
    
    @abstractmethod
    async def create_feature_subtab(
        self,
        document_id: str,
        epic_tab_id: str,
        feature_doc: FeatureDocumentation,
    ) -> bool:
        """Create feature subtab within an Epic tab.
        
        Args:
            document_id: Google Docs document ID
            epic_tab_id: Parent Epic tab ID
            feature_doc: Feature documentation to create
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If subtab creation fails
        """
        pass
    
    @abstractmethod
    async def update_feature_documentation(
        self,
        document_id: str,
        epic_tab_id: str,
        feature_doc: FeatureDocumentation,
    ) -> bool:
        """Update existing feature documentation.
        
        Args:
            document_id: Google Docs document ID
            epic_tab_id: Parent Epic tab ID
            feature_doc: Updated feature documentation
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If update fails
        """
        pass
    
    @abstractmethod
    async def apply_document_formatting(
        self,
        document_id: str,
        formatting: DocumentFormatting,
    ) -> bool:
        """Apply formatting settings to document.
        
        Args:
            document_id: Google Docs document ID
            formatting: Formatting settings to apply
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If formatting fails
        """
        pass
    
    @abstractmethod
    async def set_tab_color(
        self,
        document_id: str,
        tab_id: str,
        color_code: str,
    ) -> bool:
        """Set color for a specific tab/section.
        
        Args:
            document_id: Google Docs document ID
            tab_id: Tab ID to color
            color_code: Color code (RED, YELLOW, GREEN)
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If coloring fails
        """
        pass
    
    @abstractmethod
    async def insert_table(
        self,
        document_id: str,
        tab_id: str,
        table_data: List[List[str]],
        position: int,
    ) -> bool:
        """Insert a table at specified position.
        
        Args:
            document_id: Google Docs document ID
            tab_id: Tab ID where table should be inserted
            table_data: 2D list of table data
            position: Position index to insert table
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If insertion fails
        """
        pass
    
    @abstractmethod
    async def add_hyperlink(
        self,
        document_id: str,
        tab_id: str,
        text: str,
        url: str,
        position: int,
    ) -> bool:
        """Add hyperlink at specified position.
        
        Args:
            document_id: Google Docs document ID
            tab_id: Tab ID where hyperlink should be added
            text: Display text for hyperlink
            url: URL to link to
            position: Position index to insert hyperlink
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If hyperlink addition fails
        """
        pass
    
    @abstractmethod
    async def tag_user_by_email(
        self,
        document_id: str,
        tab_id: str,
        email: str,
        position: int,
    ) -> bool:
        """Tag user by email in document.
        
        Args:
            document_id: Google Docs document ID
            tab_id: Tab ID where user should be tagged
            email: User email to tag
            position: Position index to tag user
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If tagging fails
        """
        pass
    
    @abstractmethod
    async def get_document_structure(
        self,
        document_id: str,
    ) -> GoogleDocsStructure:
        """Get current document structure.
        
        Args:
            document_id: Google Docs document ID
            
        Returns:
            GoogleDocsStructure with current tabs and content
            
        Raises:
            Exception: If retrieval fails
        """
        pass
    
    @abstractmethod
    async def list_epic_tabs(self, document_id: str) -> List[EpicTab]:
        """List all Epic tabs in document.
        
        Args:
            document_id: Google Docs document ID
            
        Returns:
            List of EpicTab entities
            
        Raises:
            Exception: If listing fails
        """
        pass
    
    @abstractmethod
    async def feature_subtab_exists(
        self,
        document_id: str,
        epic_tab_id: str,
        feature_title: str,
    ) -> bool:
        """Check if feature subtab exists.
        
        Args:
            document_id: Google Docs document ID
            epic_tab_id: Parent Epic tab ID
            feature_title: Title of feature to check
            
        Returns:
            True if subtab exists, False otherwise
            
        Raises:
            Exception: If check fails
        """
        pass
    
    @abstractmethod
    async def get_or_create_feature_subtab(
        self,
        document_id: str,
        epic_tab_id: str,
        feature_doc: FeatureDocumentation,
    ) -> tuple[str, bool]:
        """Get existing or create new feature subtab.
        
        Args:
            document_id: Google Docs document ID
            epic_tab_id: Parent Epic tab ID
            feature_doc: Feature documentation
            
        Returns:
            Tuple of (subtab_id, created) where created is True if newly created
            
        Raises:
            Exception: If operation fails
        """
        pass
    
    @abstractmethod
    async def delete_feature_subtab(
        self,
        document_id: str,
        epic_tab_id: str,
        feature_title: str,
    ) -> bool:
        """Delete feature subtab.
        
        Args:
            document_id: Google Docs document ID
            epic_tab_id: Parent Epic tab ID
            feature_title: Title of feature to delete
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If deletion fails
        """
        pass
    
    @abstractmethod
    async def insert_table_of_contents(
        self,
        document_id: str,
        tab_id: str,
        position: int,
    ) -> bool:
        """Insert table of contents at specified position.
        
        Args:
            document_id: Google Docs document ID
            tab_id: Tab ID where TOC should be inserted
            position: Position index to insert TOC
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If insertion fails
        """
        pass
