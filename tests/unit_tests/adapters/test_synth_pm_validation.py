"""Unit tests for feature validation logic in SynthPM."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from unittest.mock import Mock

from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.project_config import (
    BoardConfig,
    ProjectBoardsConfig,
    ProjectConfig,
    ProjectInfo,
    ProjectMetadata,
    ProjectStatusMapping,
    SyncSettings,
    TelegramConfig,
)
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings


def create_test_feature(**overrides) -> SynthPMFeatureEntity:
    """Factory function to create test feature with defaults."""
    defaults = {
        "row_number": 1,
        "sheet_row_number": 2,
        "task_title": "Test Feature",
        "status": "۵. آماده پیاده سازی فنی",
        "involved_people": "User1",
        "sprint": "Sprint-1",
        "ai": "✓",
        "implementation_start_date": "2024-01-01",
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)


class TestFeatureValidation(unittest.TestCase):
    """Test feature validation logic."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock settings with project config
        self.settings = Mock(spec=SynthPMSettings)
        
        # Create test project config
        self.project_config = ProjectConfig(
            project_key="TEST",
            spreadsheet_id="test123",
            boards=ProjectBoardsConfig(
                developer_board=BoardConfig(
                    jira_board_key="TEST",
                    sheet_name="Test Sheet",
                    data_range="A2:AY",
                ),
            ),
            telegram=TelegramConfig(
                bot_token_env="TEST_BOT_TOKEN",
                channel_id_env="TEST_CHANNEL_ID",
                group_id_env="TEST_GROUP_ID",
            ),
            sync_settings=SyncSettings(
                minimum_status_for_task_creation="۵. آماده پیاده سازی فنی",
            ),
        )
        
        # Create test project metadata with status mappings
        self.project_metadata = ProjectMetadata(
            project_info=ProjectInfo(
                description="Test Project",
                key="TEST",
                start_date="2024-01-01",
                keywords=["test"],
            ),
            status_mapping=ProjectStatusMapping(
                google_sheet_to_jira={
                    "۱. ثبت و اولویت بندی": "BACKLOG",
                    "۵. آماده پیاده سازی فنی": "OPEN",
                    "۶. در حال پیاده سازی": "IN PROGRESS",
                },
                jira_to_google_sheet={
                    "BACKLOG": "۱. ثبت و اولویت بندی",
                    "OPEN": "۵. آماده پیاده سازی فنی",
                    "IN PROGRESS": "۶. در حال پیاده سازی",
                },
            ),
            sprint_configuration={},
            departments={},
            components=[],
            assignees=[],
            epics=[],
        )
        
        self.settings.get_project_config.return_value = self.project_config
        self.settings.get_project_metadata.return_value = self.project_metadata
        
        # Create repository with mocks
        self.google_sheet_client = MagicMock()
        self.jira_repository = MagicMock()
        self.jira_repository.get_board_id.return_value = 123
        self.user_config = MagicMock()
        
        self.repository = SynthPMRepository(
            google_sheet_client=self.google_sheet_client,
            jira_repository=self.jira_repository,
            settings=self.settings,
            user_config=self.user_config,
            project_key="TEST",
        )

    def test_validate_empty_title(self):
        """Test validation fails for empty task title."""
        feature = create_test_feature(task_title="")
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertFalse(is_valid)
        self.assertIn("title", error.lower())

    def test_validate_status_below_minimum(self):
        """Test validation fails for status below minimum."""
        feature = create_test_feature(
            status="۳. آماده سازی یوزر استوری",  # Below minimum
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(
            feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        
        self.assertFalse(is_valid)
        self.assertIn("below minimum", error.lower())

    def test_validate_status_at_minimum(self):
        """Test validation passes for status at minimum threshold."""
        feature = create_test_feature(
            status="۵. آماده پیاده سازی فنی",  # At minimum
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(
            feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_no_assignees(self):
        """Test validation fails when no assignees defined."""
        feature = create_test_feature(
            involved_people="",  # Empty
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertFalse(is_valid)
        self.assertIn("assignees", error.lower())

    def test_validate_no_sprint(self):
        """Test validation fails when no sprint defined."""
        feature = create_test_feature(
            sprint=None,  # No sprint
            sprint_list=None,
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertFalse(is_valid)
        self.assertIn("sprint", error.lower())

    def test_validate_no_departments(self):
        """Test validation fails when no departments/components defined."""
        feature = create_test_feature(
            ai=None,  # All departments empty
            backend=None,
            frontend=None,
            devops=None,
            ui_ux=None,
            qa_pm=None,
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertFalse(is_valid)
        self.assertIn("department", error.lower())

    def test_validate_no_dates(self):
        """Test validation fails when no dates defined."""
        feature = create_test_feature(
            implementation_start_date=None,  # No dates
            deadline=None,
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertFalse(is_valid)
        self.assertIn("date", error.lower())

    def test_validate_all_requirements_met(self):
        """Test validation passes when all requirements are met."""
        feature = create_test_feature(
            status="۶. در حال پیاده سازی",
            involved_people="User1, User2",
            backend="✓",
            deadline="2024-01-31",
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_with_sprint_list(self):
        """Test validation passes with sprint_list instead of sprint."""
        feature = create_test_feature(
            sprint=None,
            sprint_list=["1:Sprint-1:2024-01-01:2024-01-07"],
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_different_departments(self):
        """Test validation passes with different department combinations."""
        # Test with backend only
        feature = create_test_feature(
            task_title="Backend Feature",
            ai=None,
            backend="✓",
        )
        
        is_valid, _ = self.repository.validate_feature_for_task_creation(feature)
        self.assertTrue(is_valid)
        
        # Test with UI/UX only
        feature_uiux = create_test_feature(
            task_title="UI Feature",
            ai=None,
            backend=None,
            ui_ux="✓",
        )
        
        is_valid, _ = self.repository.validate_feature_for_task_creation(feature)
        self.assertTrue(is_valid)
        
        # Test with QA/PM only
        feature_qapm = create_test_feature(
            task_title="QA Feature",
            ai=None,
            backend=None,
            qa_pm="✓",
        )
        
        is_valid, _ = self.repository.validate_feature_for_task_creation(feature_qapm)
        self.assertTrue(is_valid)

    def test_validate_invalid_status(self):
        """Test validation fails for invalid status value."""
        feature = create_test_feature(
            status="Invalid Status",
        )
        
        is_valid, error = self.repository.validate_feature_for_task_creation(feature)
        
        self.assertFalse(is_valid)
        self.assertIn("invalid status", error.lower())


if __name__ == "__main__":
    unittest.main()
