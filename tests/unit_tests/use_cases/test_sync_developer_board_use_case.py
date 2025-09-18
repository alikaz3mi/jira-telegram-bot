"""Unit tests for SyncDeveloperBoardUseCase."""
from __future__ import annotations

import unittest
from unittest.mock import Mock
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.adapters.synth_pm.google_sheets_adapter import (
    SynthPMGoogleSheetsAdapter,
)
from jira_telegram_bot.adapters.synth_pm.jira_adapter import SynthPMJiraAdapter
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.synth_pm.sync_developer_board_use_case import (
    SyncDeveloperBoardUseCase,
)


class TestSyncDeveloperBoardUseCase(unittest.TestCase):
    """Test cases for SyncDeveloperBoardUseCase sprint selection logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_adapter = Mock(spec=SynthPMJiraAdapter)
        self.mock_google_sheets_adapter = Mock(spec=SynthPMGoogleSheetsAdapter)
        self.mock_user_config = Mock(spec=UserConfigInterface)
        
        # Setup mock jira adapter properties
        self.mock_jira_adapter.developer_board_id = 123
        self.mock_jira_adapter.jira_repository = Mock()
        
        self.use_case = SyncDeveloperBoardUseCase(
            google_sheets_adapter=self.mock_google_sheets_adapter,
            jira_adapter=self.mock_jira_adapter,
            user_config=self.mock_user_config,
        )

    def test_select_best_sprint_from_list_empty_list(self):
        """Test sprint selection with empty list."""
        # Act
        result = self.use_case._select_best_sprint_from_list([])
        
        # Assert
        self.assertEqual(result, "")

    def test_select_best_sprint_from_list_single_sprint(self):
        """Test sprint selection with single sprint."""
        # Arrange
        sprint_list = ["49: 06-15 to 06-21"]
        
        # Act
        result = self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert
        self.assertEqual(result, "49: 06-15 to 06-21")

    def test_select_best_sprint_from_list_multiple_sprints_no_active(self):
        """Test sprint selection with multiple sprints when no active sprint."""
        # Arrange
        sprint_list = ["49: 06-15 to 06-21", "50: 06-22 to 06-28", "51: 06-29 to 07-05"]
        
        # Mock _find_active_sprint to return None
        self.use_case._find_active_sprint = Mock(return_value=None)
        
        # Act
        result = self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert - Should return first sprint as fallback
        self.assertEqual(result, "49: 06-15 to 06-21")

    def test_select_best_sprint_from_list_with_active_sprint(self):
        """Test sprint selection when active sprint is found."""
        # Arrange
        sprint_list = ["49: 06-15 to 06-21", "50: 06-22 to 06-28", "51: 06-29 to 07-05"]
        
        # Mock _find_active_sprint to return specific sprint
        self.use_case._find_active_sprint = Mock(return_value="50: 06-22 to 06-28")
        
        # Act
        result = self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert
        self.assertEqual(result, "50: 06-22 to 06-28")

    def test_select_best_sprint_from_list_invalid_sprint_format(self):
        """Test sprint selection with invalid sprint format."""
        # Arrange
        sprint_list = ["invalid-format", "49: 06-15 to 06-21"]
        
        # Mock _find_active_sprint to return None
        self.use_case._find_active_sprint = Mock(return_value=None)
        
        # Act
        result = self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert - Should return first valid parsed sprint
        self.assertEqual(result, "49: 06-15 to 06-21")

    def test_select_best_sprint_from_list_all_invalid_format(self):
        """Test sprint selection when all sprints have invalid format."""
        # Arrange
        sprint_list = ["invalid-format", "another-invalid"]
        
        # Act
        result = self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert - Should fallback to first sprint
        self.assertEqual(result, "invalid-format")

    def test_find_active_sprint_with_active_sprint(self):
        """Test finding active sprint when one exists."""
        # Arrange
        parsed_sprints = [
            ("49: 06-15 to 06-21", SprintInfo(sprint_id="49", start_date="06-15", end_date="06-21")),
            ("50: 06-22 to 06-28", SprintInfo(sprint_id="50", start_date="06-22", end_date="06-28")),
        ]
        
        # Mock Jira sprint response
        mock_sprint_1 = Mock()
        mock_sprint_1.name = "49"
        mock_sprint_1.state = "closed"
        
        mock_sprint_2 = Mock()
        mock_sprint_2.name = "50"
        mock_sprint_2.state = "active"
        
        self.mock_jira_adapter.jira_repository.jira.sprints.return_value = [
            mock_sprint_1, mock_sprint_2
        ]
        
        # Act
        result = self.use_case._find_active_sprint(parsed_sprints)
        
        # Assert
        self.assertEqual(result, "50: 06-22 to 06-28")
        self.mock_jira_adapter.jira_repository.jira.sprints.assert_called_once_with(
            123, extended=True
        )

    def test_find_active_sprint_no_active_sprint(self):
        """Test finding active sprint when none exists."""
        # Arrange
        parsed_sprints = [
            ("49: 06-15 to 06-21", SprintInfo(sprint_id="49", start_date="06-15", end_date="06-21")),
        ]
        
        # Mock Jira sprint response - no active sprints
        mock_sprint = Mock()
        mock_sprint.name = "49"
        mock_sprint.state = "closed"
        
        self.mock_jira_adapter.jira_repository.jira.sprints.return_value = [mock_sprint]
        
        # Act
        result = self.use_case._find_active_sprint(parsed_sprints)
        
        # Assert
        self.assertIsNone(result)

    def test_find_active_sprint_jira_exception(self):
        """Test finding active sprint when Jira API throws exception."""
        # Arrange
        parsed_sprints = [
            ("49: 06-15 to 06-21", SprintInfo(sprint_id="49", start_date="06-15", end_date="06-21")),
        ]
        
        # Mock Jira to raise exception
        self.mock_jira_adapter.jira_repository.jira.sprints.side_effect = Exception("Jira error")
        
        # Act
        result = self.use_case._find_active_sprint(parsed_sprints)
        
        # Assert
        self.assertIsNone(result)

    def test_find_active_sprint_no_matching_sprint(self):
        """Test finding active sprint when active sprint doesn't match our list."""
        # Arrange
        parsed_sprints = [
            ("49: 06-15 to 06-21", SprintInfo(sprint_id="49", start_date="06-15", end_date="06-21")),
        ]
        
        # Mock Jira sprint response - active sprint with different ID
        mock_sprint = Mock()
        mock_sprint.name = "52"  # Different sprint ID
        mock_sprint.state = "active"
        
        self.mock_jira_adapter.jira_repository.jira.sprints.return_value = [mock_sprint]
        
        # Act
        result = self.use_case._find_active_sprint(parsed_sprints)
        
        # Assert
        self.assertIsNone(result)

    def test_find_active_sprint_sprint_without_state(self):
        """Test finding active sprint when sprint object has no state attribute."""
        # Arrange
        parsed_sprints = [
            ("49: 06-15 to 06-21", SprintInfo(sprint_id="49", start_date="06-15", end_date="06-21")),
        ]
        
        # Mock Jira sprint response - sprint without state
        mock_sprint = Mock()
        mock_sprint.name = "49"
        # Don't set state attribute
        
        self.mock_jira_adapter.jira_repository.jira.sprints.return_value = [mock_sprint]
        
        # Act
        result = self.use_case._find_active_sprint(parsed_sprints)
        
        # Assert
        self.assertIsNone(result)

    @patch('jira_telegram_bot.use_cases.synth_pm.sync_developer_board_use_case.SprintInfo')
    def test_select_best_sprint_calls_sprint_info_parse(self, mock_sprint_info):
        """Test that sprint selection properly calls SprintInfo.parse_sprint_string."""
        # Arrange
        sprint_list = ["49: 06-15 to 06-21", "50: 06-22 to 06-28"]
        
        # Mock SprintInfo.parse_sprint_string
        mock_parsed_sprint = Mock()
        mock_parsed_sprint.sprint_id = "49"
        mock_sprint_info.parse_sprint_string.return_value = mock_parsed_sprint
        
        # Mock _find_active_sprint to return None
        self.use_case._find_active_sprint = Mock(return_value=None)
        
        # Act
        self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert
        self.assertEqual(mock_sprint_info.parse_sprint_string.call_count, 2)
        mock_sprint_info.parse_sprint_string.assert_any_call("49: 06-15 to 06-21")
        mock_sprint_info.parse_sprint_string.assert_any_call("50: 06-22 to 06-28")

    def test_select_best_sprint_integration_with_real_sprint_info(self):
        """Integration test with real SprintInfo parsing."""
        # Arrange
        sprint_list = ["49: 06-15 to 06-21", "50: 06-22 to 06-28"]
        
        # Mock _find_active_sprint to return None
        self.use_case._find_active_sprint = Mock(return_value=None)
        
        # Act
        result = self.use_case._select_best_sprint_from_list(sprint_list)
        
        # Assert - Should return first sprint
        self.assertEqual(result, "49: 06-15 to 06-21")
        # Verify _find_active_sprint was called with properly parsed sprints
        call_args = self.use_case._find_active_sprint.call_args[0][0]
        self.assertEqual(len(call_args), 2)
        self.assertEqual(call_args[0][0], "49: 06-15 to 06-21")
        self.assertEqual(call_args[0][1].sprint_id, "49")
        self.assertEqual(call_args[1][0], "50: 06-22 to 06-28")
        self.assertEqual(call_args[1][1].sprint_id, "50")


if __name__ == "__main__":
    unittest.main()