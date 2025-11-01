"""Unit tests for documentation helper classes."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from jira_telegram_bot.entities.synth_pm.pm_board_features import (
    SynthPMFeatureEntity,
)
from jira_telegram_bot.use_cases.helpers.documentation_helpers import (
    DocumentationSubtaskHelper,
)
from jira_telegram_bot.use_cases.helpers.documentation_helpers import (
    EmailMappingHelper,
)
from jira_telegram_bot.use_cases.helpers.documentation_helpers import (
    ReleaseCreationHelper,
)


class TestDocumentationSubtaskHelper(unittest.TestCase):
    """Test cases for DocumentationSubtaskHelper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="8",
            backend="16",
            ui_ux="4",
            ai="0",
            devops="",
        )
    
    def test_create_documentation_task_info(self):
        """Test creating documentation task info."""
        task_info = DocumentationSubtaskHelper.create_documentation_task_info(
            parent_issue_key="FEAT-1",
            department="Frontend",
            assignee_email="dev@example.com",
            feature=self.feature,
        )
        
        self.assertEqual(task_info.department, "Frontend")
        self.assertEqual(task_info.assignee_email, "dev@example.com")
        self.assertEqual(task_info.estimated_hours, 2)
        self.assertEqual(task_info.parent_issue_key, "FEAT-1")
        self.assertIn("مستندسازی Frontend", task_info.task_title)
    
    def test_extract_departments_with_times(self):
        """Test extracting departments with time estimates."""
        departments = DocumentationSubtaskHelper.extract_departments_with_times(
            self.feature,
        )
        
        self.assertEqual(len(departments), 3)
        self.assertEqual(departments["Frontend"], 8)
        self.assertEqual(departments["Backend"], 16)
        self.assertEqual(departments["UI/UX"], 4)
        self.assertNotIn("AI", departments)
        self.assertNotIn("DevOps", departments)
    
    def test_extract_departments_all_zero(self):
        """Test extracting departments when all are zero."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="0",
            backend="0",
            ui_ux="0",
            ai="0",
            devops="0",
        )
        
        departments = DocumentationSubtaskHelper.extract_departments_with_times(
            feature,
        )
        
        self.assertEqual(len(departments), 0)
    
    def test_should_create_documentation_subtask(self):
        """Test checking if documentation subtask should be created."""
        self.assertTrue(
            DocumentationSubtaskHelper.should_create_documentation_subtask(
                "Frontend",
                8,
            ),
        )
        
        self.assertFalse(
            DocumentationSubtaskHelper.should_create_documentation_subtask(
                "Frontend",
                0,
            ),
        )
    
    def test_build_documentation_subtask_description(self):
        """Test building documentation subtask description."""
        description = DocumentationSubtaskHelper.build_documentation_subtask_description(
            self.feature,
            "Frontend",
        )
        
        self.assertIn("# مستندسازی Frontend", description)
        self.assertIn("## فیچر: Test Feature", description)
        self.assertIn("## وظایف مستندسازی:", description)
        self.assertIn("## زمان تخمینی: 2 ساعت", description)


class TestReleaseCreationHelper(unittest.TestCase):
    """Test cases for ReleaseCreationHelper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.release_note = MagicMock()
        self.release_note.release_version = "v1.0.0"
        self.release_note.description = "Test Release"
        self.release_note.start_date = "2025-11-01"
        self.release_note.beta_delivery = "2025-11-15"
    
    def test_extract_release_info(self):
        """Test extracting release information."""
        release_info = ReleaseCreationHelper.extract_release_info(
            self.release_note,
        )
        
        self.assertEqual(release_info["name"], "v1.0.0")
        self.assertEqual(release_info["description"], "Test Release")
        self.assertEqual(release_info["startDate"], "2025-11-01")
        self.assertEqual(release_info["releaseDate"], "2025-11-15")
        self.assertFalse(release_info["archived"])
        self.assertFalse(release_info["released"])
    
    def test_extract_release_info_without_dates(self):
        """Test extracting release info without dates."""
        release_note = MagicMock()
        release_note.release_version = "v1.0.0"
        release_note.description = "Test Release"
        release_note.start_date = None
        release_note.beta_delivery = None
        
        release_info = ReleaseCreationHelper.extract_release_info(release_note)
        
        self.assertNotIn("startDate", release_info)
        self.assertNotIn("releaseDate", release_info)
    
    def test_should_create_release_when_not_exists(self):
        """Test should_create_release when release doesn't exist."""
        existing_releases = ["v0.9.0", "v0.9.5"]
        
        should_create = ReleaseCreationHelper.should_create_release(
            self.release_note,
            existing_releases,
        )
        
        self.assertTrue(should_create)
    
    def test_should_not_create_release_when_exists(self):
        """Test should_create_release when release already exists."""
        existing_releases = ["v0.9.0", "v1.0.0", "v1.1.0"]
        
        should_create = ReleaseCreationHelper.should_create_release(
            self.release_note,
            existing_releases,
        )
        
        self.assertFalse(should_create)


class TestEmailMappingHelper(unittest.TestCase):
    """Test cases for EmailMappingHelper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_config_interface = MagicMock()
        
        user1 = MagicMock()
        user1.name = "John Doe"
        user1.email = "john@example.com"
        user1.people_column = "Frontend"
        
        user2 = MagicMock()
        user2.name = "Jane Smith"
        user2.email = "jane@example.com"
        user2.people_column = "Backend"
        
        self.user_config_interface.get_all_user_configs.return_value = {
            "user1": user1,
            "user2": user2,
        }
        
        self.feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="Frontend: John",
            backend="Backend: Jane",
        )
    
    def test_get_user_email_by_name(self):
        """Test getting user email by name."""
        email = EmailMappingHelper.get_user_email_by_name(
            self.user_config_interface,
            "John Doe",
        )
        
        self.assertEqual(email, "john@example.com")
    
    def test_get_user_email_by_name_not_found(self):
        """Test getting user email when not found."""
        email = EmailMappingHelper.get_user_email_by_name(
            self.user_config_interface,
            "Nonexistent User",
        )
        
        self.assertIsNone(email)
    
    def test_get_department_assignee_from_feature(self):
        """Test getting department assignee from feature."""
        email = EmailMappingHelper.get_department_assignee_from_feature(
            self.user_config_interface,
            self.feature,
            "Frontend",
        )
        
        self.assertEqual(email, "john@example.com")
    
    def test_get_department_assignee_not_found(self):
        """Test getting department assignee when not found."""
        email = EmailMappingHelper.get_department_assignee_from_feature(
            self.user_config_interface,
            self.feature,
            "DevOps",
        )
        
        self.assertIsNone(email)
    
    def test_get_department_assignee_with_zero_time(self):
        """Test getting assignee for department with zero time."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="0",
            backend="Backend: Jane",
        )
        
        email = EmailMappingHelper.get_department_assignee_from_feature(
            self.user_config_interface,
            feature,
            "Frontend",
        )
        
        self.assertIsNone(email)


class TestDocumentationSubtaskHelperEdgeCases(unittest.TestCase):
    """Test edge cases for DocumentationSubtaskHelper."""
    
    def test_extract_departments_with_invalid_values(self):
        """Test extracting departments with invalid time values."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="invalid",
            backend="16",
            ui_ux="",
            ai=None,
        )
        
        departments = DocumentationSubtaskHelper.extract_departments_with_times(
            feature,
        )
        
        self.assertNotIn("Frontend", departments)
        self.assertEqual(departments["Backend"], 16)
        self.assertNotIn("UI/UX", departments)
        self.assertNotIn("AI", departments)
    
    def test_extract_departments_with_float_values(self):
        """Test extracting departments with float time values."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="8.5",
            backend="16.75",
        )
        
        departments = DocumentationSubtaskHelper.extract_departments_with_times(
            feature,
        )
        
        self.assertEqual(departments["Frontend"], 8)
        self.assertEqual(departments["Backend"], 16)
    
    def test_build_description_with_no_description(self):
        """Test building description when feature has no description."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            description=None,
        )
        
        description = DocumentationSubtaskHelper.build_documentation_subtask_description(
            feature,
            "Frontend",
        )
        
        self.assertIn("توضیحات در دسترس نیست", description)


if __name__ == "__main__":
    unittest.main()
