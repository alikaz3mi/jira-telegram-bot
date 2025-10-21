"""Unit tests for SyncBugImprovementToSheetsUseCase."""
import unittest
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import Mock

from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSheetRow
from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSyncConfig
from jira_telegram_bot.entities.bugs_synchronization import SheetBoardMapping
from jira_telegram_bot.use_cases.bugs_synchronization import (
    SyncBugImprovementToSheetsUseCase,
)


class TestSyncBugImprovementToSheetsUseCase(unittest.IsolatedAsyncioTestCase):
    """Test SyncBugImprovementToSheetsUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_fetch_use_case = Mock()
        self.mock_sheets_gateway = Mock()
        self.jira_base_url = "https://jira.example.com"

        self.mapping = SheetBoardMapping(
            spreadsheet_id="test-sheet-id",
            sheet_name="Bugs",
            board_key="TEST",
            gid=12345,
        )

        self.sync_config = BugImprovementSyncConfig(
            mappings=[self.mapping],
        )

        self.use_case = SyncBugImprovementToSheetsUseCase(
            fetch_data_use_case=self.mock_fetch_use_case,
            sheets_gateway=self.mock_sheets_gateway,
            sync_config=self.sync_config,
            jira_base_url=self.jira_base_url,
        )

    async def test_aexecute_for_board_full_sync(self):
        """Test executing full sync for a single board."""
        test_row = self._create_test_row("TEST-1", "Bug 1")
        self.mock_fetch_use_case.execute.return_value = [test_row]
        self.mock_sheets_gateway.update_cells = AsyncMock(return_value=True)

        result = await self.use_case.execute_for_board("TEST", days_back=None)

        self.assertTrue(result)
        self.mock_fetch_use_case.execute.assert_called_once_with("TEST", None)
        self.mock_sheets_gateway.update_cells.assert_called_once()

    async def test_aexecute_for_board_incremental_sync(self):
        """Test executing incremental sync for a single board."""
        test_row = self._create_test_row("TEST-1", "Bug 1")
        self.mock_fetch_use_case.execute.return_value = [test_row]
        self.mock_sheets_gateway.get_sheet_values = AsyncMock(return_value=[])
        self.mock_sheets_gateway.update_cells = AsyncMock(return_value=True)
        self.mock_sheets_gateway.append_rows = AsyncMock(return_value=True)

        result = await self.use_case.execute_for_board("TEST", days_back=7)

        self.assertTrue(result)
        self.mock_fetch_use_case.execute.assert_called_once_with("TEST", 7)

    async def test_aexecute_for_board_no_data(self):
        """Test executing sync when no data is returned."""
        self.mock_fetch_use_case.execute.return_value = []

        result = await self.use_case.execute_for_board("TEST")

        self.assertTrue(result)
        self.mock_fetch_use_case.execute.assert_called_once()
        self.mock_sheets_gateway.update_cells.assert_not_called()

    async def test_aexecute_for_all_boards(self):
        """Test executing sync for all configured boards."""
        test_row = self._create_test_row("TEST-1", "Bug 1")
        self.mock_fetch_use_case.execute.return_value = [test_row]
        self.mock_sheets_gateway.update_cells = AsyncMock(return_value=True)

        result = await self.use_case.execute_for_all_boards()

        self.assertTrue(result)
        self.assertEqual(self.mock_fetch_use_case.execute.call_count, 1)

    def test_convert_row_to_values(self):
        """Test converting BugImprovementSheetRow to list of values."""
        row = self._create_test_row("TEST-1", "Test Bug")

        values = self.use_case._convert_row_to_values(row)

        self.assertEqual(len(values), 17)
        self.assertEqual(values[0], 1)
        self.assertEqual(values[1], "Test Bug")
        self.assertEqual(values[6], "Open")
        self.assertIn("TEST-1", values[16])

    def test_format_date_with_datetime(self):
        """Test formatting datetime to string."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = self.use_case._format_date(dt)

        self.assertEqual(result, "2024-01-15 10:30:45")

    def test_format_date_with_none(self):
        """Test formatting None date returns empty string."""
        result = self.use_case._format_date(None)

        self.assertEqual(result, "")

    def test_renumber_rows(self):
        """Test renumbering rows sequentially."""
        rows = [
            self._create_test_row("TEST-1", "Bug 1"),
            self._create_test_row("TEST-2", "Bug 2"),
            self._create_test_row("TEST-3", "Bug 3"),
        ]

        self.use_case._renumber_rows(rows)

        self.assertEqual(rows[0].row_number, 1)
        self.assertEqual(rows[1].row_number, 2)
        self.assertEqual(rows[2].row_number, 3)

    def test_extract_issue_keys(self):
        """Test extracting issue keys from sheet data."""
        data = [
            ["1", "Bug 1", "", "", "", "", "Open", "", "", "0", "", "", "", "", "", "", "TEST-1"],
            ["2", "Bug 2", "", "", "", "", "Open", "", "", "0", "", "", "", "", "", "", "TEST-2"],
        ]

        result = self.use_case._extract_issue_keys(data)

        self.assertEqual(result, ["TEST-1", "TEST-2"])

    def test_merge_data(self):
        """Test merging existing data with updated rows."""
        existing_data = [
            ["1", "Old Bug", "", "", "", "", "Open", "", "", "0", "", "", "", "", "", "", "TEST-1"],
        ]

        update_row = self._create_test_row("TEST-1", "Updated Bug")
        all_rows = [update_row]

        result = self.use_case._merge_data(existing_data, [update_row], all_rows)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_title, "Updated Bug")

    def _create_test_row(self, key, title):
        """Create a test BugImprovementSheetRow.

        Args:
            key: Issue key.
            title: Issue title.

        Returns:
            BugImprovementSheetRow instance.
        """
        return BugImprovementSheetRow(
            row_number=1,
            task_title=title,
            description="Test description",
            epic_name=None,
            linked_story=None,
            priority="Medium",
            status="Open",
            departments=["Backend"],
            release=None,
            total_hours=0.0,
            involved_people=[],
            created_date=datetime(2024, 1, 15),
            implementation_start_date=None,
            deadline=None,
            sprint=None,
            initial_delivery_time=None,
            issue_key=key,
        )


if __name__ == "__main__":
    unittest.main()
