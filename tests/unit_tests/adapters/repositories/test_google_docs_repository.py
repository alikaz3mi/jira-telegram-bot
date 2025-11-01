"""Unit tests for GoogleDocsRepository."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.adapters.repositories.google_docs_repository import (
    GoogleDocsRepository,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    AcceptanceCriteriaSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    ApiListSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DepartmentChip,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentColor,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    EpicTab,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureDocumentation,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureTableInfo,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    SubtasksSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    UserStorySection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    WireframeSection,
)


class TestGoogleDocsRepository(unittest.TestCase):
    """Test cases for GoogleDocsRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.google_service_settings = MagicMock()
        self.google_service_settings.service_account_file = "test_creds.json"
        
        self.repository = GoogleDocsRepository(
            google_service_settings=self.google_service_settings,
        )
        
        self.repository._docs_service = MagicMock()
        
        self.feature_doc = FeatureDocumentation(
            feature_title="Test Feature",
            jira_issue_key="FEAT-1",
            epic_tab_id="epic_123",
            table_info=FeatureTableInfo(
                department_chips=[
                    DepartmentChip(
                        department="Frontend",
                        estimated_hours=8,
                    ),
                ],
            ),
            user_story=UserStorySection(
                title="User Story",
                content=None,
            ),
            acceptance_criteria=AcceptanceCriteriaSection(
                title="Acceptance Criteria",
                criteria=[],
            ),
            wireframe=WireframeSection(
                title="Wireframe",
                wireframe_links=[],
            ),
            api_list=ApiListSection(
                title="API List for FEAT-1",
                api_items=[],
            ),
            subtasks=SubtasksSection(
                title="Subtasks",
                subtasks=[],
            ),
            color_code=DocumentColor.DEFAULT,
        )


class TestGetOrCreateEpicTab(TestGoogleDocsRepository):
    """Test getting or creating epic tabs."""
    
    def test_get_or_create_epic_tab_new(self):
        """Test creating a new epic tab."""
        self.repository._docs_service.documents().get().execute.return_value = {
            "namedRanges": {},
        }
        
        self.repository._docs_service.documents().batchUpdate().execute.return_value = {
            "replies": [
                {"createNamedRange": {"namedRangeId": "epic_new_123"}},
            ],
        }
        
        tab_id = self.repository.get_or_create_epic_tab(
            document_id="doc_123",
            epic_name="Epic 1",
        )
        
        self.assertEqual(tab_id, "epic_new_123")
        self.repository._docs_service.documents().batchUpdate.assert_called_once()
    
    def test_get_or_create_epic_tab_existing(self):
        """Test getting an existing epic tab."""
        self.repository._docs_service.documents().get().execute.return_value = {
            "namedRanges": {
                "epic_1": {
                    "namedRangeId": "epic_existing_123",
                },
            },
        }
        
        tab_id = self.repository.get_or_create_epic_tab(
            document_id="doc_123",
            epic_name="Epic 1",
        )
        
        self.assertEqual(tab_id, "epic_existing_123")
        self.repository._docs_service.documents().batchUpdate.assert_not_called()


class TestCreateFeatureSubtab(TestGoogleDocsRepository):
    """Test creating feature subtabs."""
    
    def test_create_feature_subtab(self):
        """Test creating a feature subtab."""
        self.repository._docs_service.documents().get().execute.return_value = {
            "body": {"content": [{"endIndex": 100}]},
        }
        
        self.repository._docs_service.documents().batchUpdate().execute.return_value = {
            "replies": [
                {"createNamedRange": {"namedRangeId": "feature_456"}},
            ],
        }
        
        subtab_id = self.repository.create_feature_subtab(
            document_id="doc_123",
            epic_tab_id="epic_123",
            feature_documentation=self.feature_doc,
        )
        
        self.assertEqual(subtab_id, "feature_456")
        self.repository._docs_service.documents().batchUpdate.assert_called_once()


class TestBuildFeatureContentRequests(TestGoogleDocsRepository):
    """Test building feature content requests."""
    
    def test_build_feature_content_requests(self):
        """Test building content requests for feature."""
        requests = self.repository._build_feature_content_requests(
            start_index=100,
            feature_documentation=self.feature_doc,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
        
        insert_text_requests = [
            r for r in requests if "insertText" in r
        ]
        self.assertGreater(len(insert_text_requests), 0)


class TestBuildTableInfoRequests(TestGoogleDocsRepository):
    """Test building table info requests."""
    
    def test_build_table_info_requests(self):
        """Test building table info requests."""
        requests = self.repository._build_table_info_requests(
            start_index=100,
            table_info=self.feature_doc.table_info,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
        
        has_department_text = any(
            "Frontend" in str(r) for r in requests
        )
        self.assertTrue(has_department_text)


class TestBuildSectionRequests(TestGoogleDocsRepository):
    """Test building section requests."""
    
    def test_build_user_story_section_requests(self):
        """Test building user story section requests."""
        requests = self.repository._build_user_story_section_requests(
            start_index=100,
            user_story=self.feature_doc.user_story,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
        
        has_title = any(
            "User Story" in str(r) for r in requests
        )
        self.assertTrue(has_title)
    
    def test_build_acceptance_criteria_section_requests(self):
        """Test building acceptance criteria section requests."""
        requests = self.repository._build_acceptance_criteria_section_requests(
            start_index=100,
            acceptance_criteria=self.feature_doc.acceptance_criteria,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
    
    def test_build_wireframe_section_requests(self):
        """Test building wireframe section requests."""
        requests = self.repository._build_wireframe_section_requests(
            start_index=100,
            wireframe=self.feature_doc.wireframe,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
    
    def test_build_api_list_section_requests(self):
        """Test building API list section requests."""
        requests = self.repository._build_api_list_section_requests(
            start_index=100,
            api_list=self.feature_doc.api_list,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
    
    def test_build_subtasks_section_requests(self):
        """Test building subtasks section requests."""
        requests = self.repository._build_subtasks_section_requests(
            start_index=100,
            subtasks=self.feature_doc.subtasks,
        )
        
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)


class TestUtilityMethods(TestGoogleDocsRepository):
    """Test utility methods."""
    
    def test_normalize_epic_name(self):
        """Test normalizing epic name."""
        normalized = self.repository._normalize_epic_name("Epic 1: Test")
        
        self.assertEqual(normalized, "epic_1_test")
    
    def test_normalize_epic_name_with_special_chars(self):
        """Test normalizing epic name with special characters."""
        normalized = self.repository._normalize_epic_name("Epic #1 (Test)!")
        
        self.assertEqual(normalized, "epic_1_test")
    
    def test_get_document_end_index(self):
        """Test getting document end index."""
        self.repository._docs_service.documents().get().execute.return_value = {
            "body": {"content": [{"endIndex": 100}]},
        }
        
        end_index = self.repository._get_document_end_index("doc_123")
        
        self.assertEqual(end_index, 100)


class TestColorHandling(TestGoogleDocsRepository):
    """Test color handling for features."""
    
    def test_build_requests_with_red_color(self):
        """Test building requests with red color code."""
        feature_doc_red = FeatureDocumentation(
            feature_title="Test Feature",
            jira_issue_key="FEAT-1",
            epic_tab_id="epic_123",
            table_info=self.feature_doc.table_info,
            user_story=self.feature_doc.user_story,
            acceptance_criteria=self.feature_doc.acceptance_criteria,
            wireframe=self.feature_doc.wireframe,
            api_list=self.feature_doc.api_list,
            subtasks=self.feature_doc.subtasks,
            color_code=DocumentColor.RED,
        )
        
        requests = self.repository._build_feature_content_requests(
            start_index=100,
            feature_documentation=feature_doc_red,
        )
        
        self.assertIsInstance(requests, list)
    
    def test_build_requests_with_green_color(self):
        """Test building requests with green color code."""
        feature_doc_green = FeatureDocumentation(
            feature_title="Test Feature",
            jira_issue_key="FEAT-1",
            epic_tab_id="epic_123",
            table_info=self.feature_doc.table_info,
            user_story=self.feature_doc.user_story,
            acceptance_criteria=self.feature_doc.acceptance_criteria,
            wireframe=self.feature_doc.wireframe,
            api_list=self.feature_doc.api_list,
            subtasks=self.feature_doc.subtasks,
            color_code=DocumentColor.GREEN,
        )
        
        requests = self.repository._build_feature_content_requests(
            start_index=100,
            feature_documentation=feature_doc_green,
        )
        
        self.assertIsInstance(requests, list)


class TestErrorHandling(TestGoogleDocsRepository):
    """Test error handling."""
    
    def test_get_or_create_epic_tab_api_error(self):
        """Test handling API error when getting/creating epic tab."""
        self.repository._docs_service.documents().get().execute.side_effect = Exception(
            "API Error",
        )
        
        with self.assertRaises(Exception):
            self.repository.get_or_create_epic_tab(
                document_id="doc_123",
                epic_name="Epic 1",
            )
    
    def test_create_feature_subtab_api_error(self):
        """Test handling API error when creating feature subtab."""
        self.repository._docs_service.documents().get().execute.side_effect = Exception(
            "API Error",
        )
        
        with self.assertRaises(Exception):
            self.repository.create_feature_subtab(
                document_id="doc_123",
                epic_tab_id="epic_123",
                feature_documentation=self.feature_doc,
            )


class TestEpicTab(TestGoogleDocsRepository):
    """Test EpicTab entity usage."""
    
    def test_epic_tab_creation(self):
        """Test creating EpicTab entity."""
        epic_tab = EpicTab(
            epic_name="Epic 1",
            tab_id="epic_123",
            feature_subtabs=[],
        )
        
        self.assertEqual(epic_tab.epic_name, "Epic 1")
        self.assertEqual(epic_tab.tab_id, "epic_123")
        self.assertEqual(len(epic_tab.feature_subtabs), 0)


if __name__ == "__main__":
    unittest.main()
