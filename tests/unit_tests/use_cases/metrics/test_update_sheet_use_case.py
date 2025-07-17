"""Unit tests for UpdateSheetUseCase."""

import unittest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock

from jira_telegram_bot.entities.metrics.metric_event import MetricEvent
from jira_telegram_bot.entities.metrics.constants import MetricType, SheetName
from jira_telegram_bot.use_cases.metrics.update_sheet_use_case import UpdateSheetUseCase


class TestUpdateSheetUseCase(unittest.IsolatedAsyncioTestCase):
    """Test suite for UpdateSheetUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.spreadsheet_gateway = AsyncMock()
        self.user_config_repository = AsyncMock()
        self.use_case = UpdateSheetUseCase(
            self.spreadsheet_gateway, 
            self.user_config_repository
        )
    
    async def test_update_daily_scoreboard_new_row(self):
        """Test updating daily scoreboard with new row."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-1",
            metric_type=MetricType.TASK_RESOLVED,
            developer_key="john.doe@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=1.0,
            project_key="TEST",
            issue_key="TEST-123"
        )
        
        sheet_config = {
            "sheet_id": "test_sheet_id",
            "range_template": "Daily!A:G"
        }
        
        developer_mapping = {
            "display_name": "John Doe",
            "email": "john.doe@example.com"
        }
        
        self.user_config_repository.get_sheet_configuration.return_value = sheet_config
        self.user_config_repository.get_developer_sheet_mapping.return_value = developer_mapping
        self.spreadsheet_gateway.get_sheet_values.return_value = []  # Empty sheet
        self.spreadsheet_gateway.append_rows.return_value = True
        
        # Act
        result = await self.use_case.update_daily_scoreboard(event)
        
        # Assert
        self.assertTrue(result)
        self.spreadsheet_gateway.append_rows.assert_called_once()
        args = self.spreadsheet_gateway.append_rows.call_args[0]  # positional args
        self.assertEqual(args[0], "test_sheet_id")  # sheet_id
        self.assertEqual(args[2][0][0], "John Doe")  # rows[0][0] - Developer name
        self.assertEqual(args[2][0][3], 1)  # rows[0][3] - Resolved tasks
    
    async def test_update_daily_scoreboard_existing_row(self):
        """Test updating daily scoreboard with existing row."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-2",
            metric_type=MetricType.COMMIT_MADE,
            developer_key="john.doe@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=1.0,
            project_key="TEST",
            metadata={"commit_message": "Fix bug"}
        )
        
        sheet_config = {
            "sheet_id": "test_sheet_id",
            "range_template": "Daily!A:G"
        }
        
        developer_mapping = {
            "display_name": "John Doe",
            "email": "john.doe@example.com"
        }
        
        existing_data = [
            ["John Doe", "2025-07-17", 0, 0, 0.0, 2, "Previous work"]
        ]
        
        self.user_config_repository.get_sheet_configuration.return_value = sheet_config
        self.user_config_repository.get_developer_sheet_mapping.return_value = developer_mapping
        self.spreadsheet_gateway.get_sheet_values.return_value = existing_data
        self.spreadsheet_gateway.update_cells.return_value = True
        
        # Act
        result = await self.use_case.update_daily_scoreboard(event)
        
        # Assert
        self.assertTrue(result)
        self.spreadsheet_gateway.update_cells.assert_called_once()
        args = self.spreadsheet_gateway.update_cells.call_args[0]  # positional args
        self.assertEqual(args[2][0][5], 3)  # values[0][5] - Commits increased from 2 to 3
        self.assertEqual(args[2][0][6], "Fix bug")  # values[0][6] - Updated comment
    
    async def test_update_sprint_matrix_new_row(self):
        """Test updating sprint matrix with new row."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-3",
            metric_type=MetricType.TASK_CREATED,
            developer_key="jane.smith@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=1.0,
            project_key="TEST",
            sprint_id="123"
        )
        
        sheet_config = {
            "sheet_id": "test_sprint_sheet_id",
            "range_template": "Sprint!A:P"
        }
        
        developer_mapping = {
            "display_name": "Jane Smith",
            "email": "jane.smith@example.com"
        }
        
        self.user_config_repository.get_sheet_configuration.return_value = sheet_config
        self.user_config_repository.get_developer_sheet_mapping.return_value = developer_mapping
        self.spreadsheet_gateway.get_sheet_values.return_value = []  # Empty sheet
        self.spreadsheet_gateway.append_rows.return_value = True
        
        # Act
        result = await self.use_case.update_sprint_matrix(event)
        
        # Assert
        self.assertTrue(result)
        self.spreadsheet_gateway.append_rows.assert_called_once()
        args = self.spreadsheet_gateway.append_rows.call_args[0]  # positional args
        self.assertEqual(args[2][0][0], "Jane Smith")  # rows[0][0] - Developer name
        self.assertEqual(args[2][0][1], 1)  # rows[0][1] - All tasks
    
    async def test_update_sprint_matrix_no_sprint_id(self):
        """Test updating sprint matrix when event has no sprint ID."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-4",
            metric_type=MetricType.TASK_CREATED,
            developer_key="jane.smith@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=1.0,
            project_key="TEST"
            # No sprint_id
        )
        
        # Act
        result = await self.use_case.update_sprint_matrix(event)
        
        # Assert
        self.assertTrue(result)  # Should return True and skip processing
        self.user_config_repository.get_sheet_configuration.assert_not_called()
    
    def test_find_daily_row_index_found(self):
        """Test finding daily row index when row exists."""
        # Arrange
        sheet_data = [
            ["Jane Smith", "2025-07-16", 0, 1, 2.5, 3, "Work done"],
            ["John Doe", "2025-07-17", 1, 0, 1.0, 2, "Bug fixes"]
        ]
        target_date = date(2025, 7, 17)
        
        # Act
        result = self.use_case._find_daily_row_index(sheet_data, "John Doe", target_date)
        
        # Assert
        self.assertEqual(result, 1)
    
    def test_find_daily_row_index_not_found(self):
        """Test finding daily row index when row doesn't exist."""
        # Arrange
        sheet_data = [
            ["Jane Smith", "2025-07-16", 0, 1, 2.5, 3, "Work done"]
        ]
        target_date = date(2025, 7, 17)
        
        # Act
        result = self.use_case._find_daily_row_index(sheet_data, "John Doe", target_date)
        
        # Assert
        self.assertIsNone(result)
    
    def test_find_sprint_row_index_found(self):
        """Test finding sprint row index when row exists."""
        # Arrange
        sheet_data = [
            ["Jane Smith", 5, 3, 2, 1, 1, 0, 0, 0, 8.5, 2.0, 0.5, 1.0, 0, 2, 1],
            ["John Doe", 3, 2, 1, 1, 2, 0, 0, 0, 6.0, 1.0, 0.0, 0.5, 0, 1, 1]
        ]
        
        # Act
        result = self.use_case._find_sprint_row_index(sheet_data, "John Doe")
        
        # Assert
        self.assertEqual(result, 1)
    
    def test_find_sprint_row_index_not_found(self):
        """Test finding sprint row index when row doesn't exist."""
        # Arrange
        sheet_data = [
            ["Jane Smith", 5, 3, 2, 1, 1, 0, 0, 0, 8.5, 2.0, 0.5, 1.0, 0, 2, 1]
        ]
        
        # Act
        result = self.use_case._find_sprint_row_index(sheet_data, "John Doe")
        
        # Assert
        self.assertIsNone(result)
    
    def test_create_daily_row_task_resolved(self):
        """Test creating daily row for task resolved event."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-5",
            metric_type=MetricType.TASK_RESOLVED,
            developer_key="john.doe@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=1.0,
            project_key="TEST",
            metadata={"summary": "Fix authentication bug"}
        )
        
        # Act
        result = self.use_case._create_daily_row(event, "John Doe")
        
        # Assert
        self.assertEqual(result[0], "John Doe")  # Developer name
        self.assertEqual(result[1], "2025-07-17")  # Date
        self.assertEqual(result[2], 0)  # Today deadlines
        self.assertEqual(result[3], 1)  # Resolved tasks
        self.assertEqual(result[4], 0.0)  # Logged time
        self.assertEqual(result[5], 0)  # Commits
        self.assertEqual(result[6], "Fix authentication bug")  # Comments
    
    def test_create_daily_row_time_logged(self):
        """Test creating daily row for time logged event."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-6",
            metric_type=MetricType.TIME_LOGGED,
            developer_key="john.doe@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=2.5,  # 2.5 hours
            project_key="TEST"
        )
        
        # Act
        result = self.use_case._create_daily_row(event, "John Doe")
        
        # Assert
        self.assertEqual(result[4], 2.5)  # Logged time
        self.assertEqual(result[3], 0)  # No resolved tasks
    
    def test_create_sprint_row_story_resolved(self):
        """Test creating sprint row for story resolved event."""
        # Arrange
        event = MetricEvent(
            event_id="test-event-7",
            metric_type=MetricType.TASK_RESOLVED,
            developer_key="jane.smith@example.com",
            timestamp=datetime(2025, 7, 17, 10, 0, 0),
            value=1.0,
            project_key="TEST",
            metadata={"issue_type": "Story"}
        )
        
        # Act
        result = self.use_case._create_sprint_row(event, "Jane Smith")
        
        # Assert
        self.assertEqual(result[0], "Jane Smith")  # Developer name
        self.assertEqual(result[1], 0)  # All tasks (not created)
        self.assertEqual(result[2], 1)  # Completed tasks
        self.assertEqual(result[5], 1)  # Resolved stories
        self.assertEqual(result[6], 0)  # Resolved bugs


if __name__ == "__main__":
    unittest.main()
