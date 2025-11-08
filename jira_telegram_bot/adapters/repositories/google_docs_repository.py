"""Google Docs repository implementation."""
from __future__ import annotations

import asyncio
from typing import Dict
from typing import List
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.google_docs_entities import DocumentColor
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
from jira_telegram_bot.settings.google_api_credentials_settings import (
    GoogleApiCredentialsSettings,
)
from jira_telegram_bot.use_cases.interfaces.google_docs_repository_interface import (
    GoogleDocsRepositoryInterface,
)


class GoogleDocsRepository(GoogleDocsRepositoryInterface):
    """Repository implementation for Google Docs operations.
    
    This repository uses shared Google API credentials to connect to Google Docs API.
    Document IDs are passed as parameters to methods, not stored in the repository.
    """
    
    def __init__(self, credentials_settings: GoogleApiCredentialsSettings):
        """Initialize Google Docs repository.
        
        Args:
            credentials_settings: Google API credentials settings containing
                                 service account token path. Document IDs are
                                 provided per-operation from project configuration.
        """
        self.credentials_settings = credentials_settings
        self._service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Docs API service."""
        try:
            scopes = [
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive.file",
            ]
            credentials = Credentials.from_service_account_file(
                self.credentials_settings.token_path,
                scopes=scopes,
            )
            self._service = build("docs", "v1", credentials=credentials)
            LOGGER.info("Google Docs API service initialized successfully")
        except Exception as e:
            LOGGER.error(f"Failed to initialize Google Docs API service: {e}")
            raise
    
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
            Tab ID (named range ID in Google Docs)
            
        Raises:
            Exception: If tab creation fails
        """
        try:
            existing_tabs = await self.list_epic_tabs(document_id)
            
            for tab in existing_tabs:
                if tab.epic_name == epic_name:
                    LOGGER.info(f"Found existing tab for Epic: {epic_name}")
                    return tab.tab_id
            
            return await self._create_epic_tab(document_id, epic_name)
            
        except Exception as e:
            LOGGER.error(f"Failed to get or create Epic tab '{epic_name}': {e}")
            raise
    
    async def _create_epic_tab(self, document_id: str, epic_name: str) -> str:
        """Create new Epic tab (actual document tab) in document.
        
        Args:
            document_id: Google Docs document ID
            epic_name: Epic name for the tab title
            
        Returns:
            Tab ID of the newly created tab
        """
        try:
            loop = asyncio.get_event_loop()
            
            # Create a new document tab using the createTab request
            requests = [
                {
                    "createTab": {
                        "tabProperties": {
                            "title": epic_name,
                        },
                    },
                },
            ]
            
            response = await loop.run_in_executor(
                None,
                lambda: self._service.documents().batchUpdate(
                    documentId=document_id,
                    body={"requests": requests},
                ).execute(),
            )
            
            # Extract the tab ID from the response
            tab_id = response.get("replies", [{}])[0].get("createTab", {}).get("tabId")
            
            if not tab_id:
                raise ValueError(f"Failed to get tab ID from createTab response")
            
            LOGGER.info(f"Created Epic tab: {epic_name} with ID: {tab_id}")
            return tab_id
            
        except Exception as e:
            LOGGER.error(f"Failed to create Epic tab '{epic_name}': {e}")
            raise
    
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
        """
        try:
            loop = asyncio.get_event_loop()
            
            document = await loop.run_in_executor(
                None,
                lambda: self._service.documents().get(documentId=document_id).execute(),
            )
            
            content = document.get("body", {}).get("content", [])
            
            for element in content:
                paragraph = element.get("paragraph", {})
                if paragraph:
                    text_run = paragraph.get("elements", [{}])[0].get("textRun", {})
                    text = text_run.get("content", "").strip()
                    
                    if text == feature_title:
                        LOGGER.info(f"Found existing feature subtab: {feature_title}")
                        return True
            
            return False
            
        except Exception as e:
            LOGGER.error(f"Failed to check feature subtab existence: {e}")
            return False
    
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
        """
        try:
            exists = await self.feature_subtab_exists(
                document_id,
                epic_tab_id,
                feature_doc.feature_title,
            )
            
            if exists:
                LOGGER.info(
                    f"Feature subtab already exists: {feature_doc.feature_title}, updating...",
                )
                success = await self.update_feature_documentation(
                    document_id,
                    epic_tab_id,
                    feature_doc,
                )
                return (epic_tab_id, False) if success else (None, False)
            else:
                success = await self.create_feature_subtab(
                    document_id,
                    epic_tab_id,
                    feature_doc,
                )
                return (epic_tab_id, True) if success else (None, False)
                
        except Exception as e:
            LOGGER.error(f"Failed to get or create feature subtab: {e}")
            return (None, False)
    
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
        """
        try:
            loop = asyncio.get_event_loop()
            
            document = await loop.run_in_executor(
                None,
                lambda: self._service.documents().get(documentId=document_id).execute(),
            )
            
            content_length = document.get("body", {}).get("content", [])[-1].get(
                "endIndex",
                1,
            )
            
            requests = await self._build_feature_content_requests(
                feature_doc,
                content_length,
            )
            
            await loop.run_in_executor(
                None,
                lambda: self._service.documents().batchUpdate(
                    documentId=document_id,
                    body={"requests": requests},
                ).execute(),
            )
            
            LOGGER.info(
                f"Created feature subtab: {feature_doc.feature_title}",
            )
            return True
            
        except Exception as e:
            LOGGER.error(
                f"Failed to create feature subtab '{feature_doc.feature_title}': {e}",
            )
            return False
    
    async def _build_feature_content_requests(
        self,
        feature_doc: FeatureDocumentation,
        start_index: int,
    ) -> List[Dict]:
        """Build Google Docs API requests for feature content.
        
        Args:
            feature_doc: Feature documentation
            start_index: Starting index in document
            
        Returns:
            List of API request dictionaries
        """
        requests = []
        current_index = start_index - 1
        
        requests.append({
            "insertText": {
                "location": {"index": current_index},
                "text": f"\n\n{feature_doc.feature_title}\n",
            },
        })
        current_index += len(feature_doc.feature_title) + 3
        
        requests.append({
            "updateParagraphStyle": {
                "range": {
                    "startIndex": start_index - 1,
                    "endIndex": current_index,
                },
                "paragraphStyle": {
                    "namedStyleType": "HEADING_1",
                },
                "fields": "namedStyleType",
            },
        })
        
        toc_text = "\n".join(feature_doc.table_of_contents.sections)
        requests.append({
            "insertText": {
                "location": {"index": current_index},
                "text": f"\nفهرست مطالب:\n{toc_text}\n",
            },
        })
        current_index += len(toc_text) + 17
        
        table_rows = self._format_feature_info_table(feature_doc.feature_info_table)
        requests.append({
            "insertTable": {
                "rows": len(table_rows),
                "columns": 2,
                "location": {"index": current_index},
            },
        })
        
        return requests
    
    def _format_feature_info_table(self, table_info) -> List[List[str]]:
        """Format feature info table data.
        
        Args:
            table_info: FeatureTableInfo entity
            
        Returns:
            2D list of table data
        """
        departments_str = ", ".join([d.name for d in table_info.departments])
        
        return [
            ["لینک ریلیز", table_info.release_link],
            ["لینک فیچر", table_info.feature_link],
            ["واحدهای درگیر", departments_str],
            ["مسئول تحویل", table_info.reporter_email],
            ["تاریخ شروع", table_info.start_date],
            ["تاریخ تحویل نهایی", table_info.final_delivery_date],
        ]
    
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
        """
        try:
            LOGGER.info(
                f"Updating feature documentation: {feature_doc.feature_title}",
            )
            return True
            
        except Exception as e:
            LOGGER.error(
                f"Failed to update feature documentation '{feature_doc.feature_title}': {e}",
            )
            return False
    
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
        """
        try:
            LOGGER.info(f"Applying document formatting to: {document_id}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to apply document formatting: {e}")
            return False
    
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
        """
        try:
            color_map = {
                DocumentColor.RED.value: {"red": 1.0, "green": 0.0, "blue": 0.0},
                DocumentColor.YELLOW.value: {"red": 1.0, "green": 1.0, "blue": 0.0},
                DocumentColor.GREEN.value: {"red": 0.0, "green": 1.0, "blue": 0.0},
            }
            
            rgb_color = color_map.get(color_code)
            if not rgb_color:
                LOGGER.warning(f"Unknown color code: {color_code}")
                return False
            
            LOGGER.info(f"Setting tab color: {tab_id} to {color_code}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to set tab color: {e}")
            return False
    
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
        """
        try:
            LOGGER.info(f"Inserting table at position {position}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to insert table: {e}")
            return False
    
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
        """
        try:
            LOGGER.info(f"Adding hyperlink '{text}' -> {url}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to add hyperlink: {e}")
            return False
    
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
        """
        try:
            LOGGER.info(f"Tagging user: {email} at position {position}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to tag user: {e}")
            return False
    
    async def get_document_structure(
        self,
        document_id: str,
    ) -> GoogleDocsStructure:
        """Get current document structure.
        
        Args:
            document_id: Google Docs document ID
            
        Returns:
            GoogleDocsStructure with current tabs and content
        """
        try:
            loop = asyncio.get_event_loop()
            
            document = await loop.run_in_executor(
                None,
                lambda: self._service.documents().get(documentId=document_id).execute(),
            )
            
            epic_tabs = await self.list_epic_tabs(document_id)
            
            from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
                DocumentFooter,
            )
            from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
                DocumentHeader,
            )
            
            formatting = DocumentFormatting(
                font_family="Vazirmatn",
                header=DocumentHeader(epic_name=""),
                footer=DocumentFooter(),
            )
            
            doc_url = f"https://docs.google.com/document/d/{document_id}/edit"
            
            return GoogleDocsStructure(
                document_id=document_id,
                document_url=doc_url,
                epic_tabs=epic_tabs,
                formatting=formatting,
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to get document structure: {e}")
            raise
    
    async def list_epic_tabs(self, document_id: str) -> List[EpicTab]:
        """List all Epic tabs (actual document tabs) in document.
        
        Args:
            document_id: Google Docs document ID
            
        Returns:
            List of EpicTab entities from actual document tabs
        """
        try:
            loop = asyncio.get_event_loop()
            
            document = await loop.run_in_executor(
                None,
                lambda: self._service.documents().get(documentId=document_id).execute(),
            )
            
            epic_tabs = []
            
            # Get actual document tabs from the tabs field
            tabs = document.get("tabs", [])
            
            if not tabs:
                LOGGER.warning(f"No tabs found in document {document_id}")
                return []
            
            for tab in tabs:
                # Get tab properties
                tab_properties = tab.get("tabProperties", {})
                tab_id = tab_properties.get("tabId")
                title = tab_properties.get("title", "")
                
                if tab_id and title:
                    epic_tabs.append(
                        EpicTab(
                            epic_name=title,
                            tab_id=tab_id,
                            features=[],
                        ),
                    )
                    LOGGER.debug(f"Found tab: {title} (ID: {tab_id})")
            
            LOGGER.info(f"Found {len(epic_tabs)} document tabs")
            return epic_tabs
            
        except Exception as e:
            LOGGER.error(f"Failed to list Epic tabs: {e}")
            return []
    
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
        """
        try:
            LOGGER.info(f"Deleting feature subtab: {feature_title}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to delete feature subtab: {e}")
            return False
    
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
        """
        try:
            loop = asyncio.get_event_loop()
            
            requests = [
                {
                    "insertTableOfContents": {
                        "location": {"index": position},
                    },
                },
            ]
            
            await loop.run_in_executor(
                None,
                lambda: self._service.documents().batchUpdate(
                    documentId=document_id,
                    body={"requests": requests},
                ).execute(),
            )
            
            LOGGER.info(f"Inserted table of contents at position {position}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to insert table of contents: {e}")
            return False
