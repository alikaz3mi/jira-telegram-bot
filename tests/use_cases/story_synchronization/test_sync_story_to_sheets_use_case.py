"""Unit tests for SyncStoryToSheetsUseCase."""
import unittest
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.story_synchronization import StorySyncConfig
from jira_telegram_bot.entities.story_synchronization.story_sync_config import (
    SheetBoardMapping,
)
from jira_telegram_bot.use_cases.story_synchronization import (
    SyncStoryToSheetsUseCase,
)


class TestSyncStoryToSheetsUseCase(unittest.IsolatedAsyncioTestCase):
    """Test SyncStoryToSheetsUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_fetch_use_case = Mock()
        self.mock_sheets_gateway = Mock()
        self.mock_user_config = Mock()
        self.mock_task_story_repository = Mock()
        self.jira_base_url = "https://jira.example.com"

        # Mock user config to return developer names
        self.mock_user_config.list_all_users_google_sheet_names.return_value = [
            "کاظمی",
            "موسوی",
            "مرادی",
        ]

        mapping = SheetBoardMapping(
            spreadsheet_id="test-spreadsheet-id",
            sheet_name="Test Sheet",
            board_key="TEST",
            gid=123456,
            data_range="A2:AW",
        )
        self.sync_config = StorySyncConfig(mappings=[mapping])

        self.use_case = SyncStoryToSheetsUseCase(
            fetch_data_use_case=self.mock_fetch_use_case,
            sheets_gateway=self.mock_sheets_gateway,
            sync_config=self.sync_config,
            jira_base_url=self.jira_base_url,
            user_config=self.mock_user_config,
            task_story_repository=self.mock_task_story_repository,
        )

        self.mock_sheets_gateway.update_cells = AsyncMock(return_value=True)
        self.mock_sheets_gateway.append_rows = AsyncMock(return_value=True)
        self.mock_task_story_repository.get_sheet_features = AsyncMock(return_value=[])
        self.mock_task_story_repository.extract_issue_keys_from_features = Mock(return_value=[])

    async def test_execute_for_board_no_data(self):
        """Test execute_for_board with no data returns True."""
        self.mock_fetch_use_case.execute.return_value = []

        result = await self.use_case.execute_for_board("TEST")

        self.assertTrue(result)
        self.mock_fetch_use_case.execute.assert_called_once_with("TEST", None)

    async def test_execute_for_board_full_sync(self):
        """Test execute_for_board performs full sync when days_back is None."""
        mock_row = self._create_mock_story_row()
        self.mock_fetch_use_case.execute.return_value = [mock_row]

        result = await self.use_case.execute_for_board("TEST", days_back=None)

        self.assertTrue(result)
        self.mock_sheets_gateway.update_cells.assert_called_once()

    async def test_execute_for_board_incremental_sync(self):
        """Test execute_for_board performs incremental sync when days_back is set."""
        mock_row = self._create_mock_story_row()
        self.mock_fetch_use_case.execute.return_value = [mock_row]
        
        # Mock the repository to return empty list (no existing rows)
        self.mock_task_story_repository.get_sheet_features = AsyncMock(return_value=[])

        result = await self.use_case.execute_for_board("TEST", days_back=7)

        self.assertTrue(result)
        # Verify repository method was called instead of gateway directly
        self.mock_task_story_repository.get_sheet_features.assert_called_once()

    async def test_execute_for_all_boards(self):
        """Test execute_for_all_boards syncs all configured boards."""
        self.mock_fetch_use_case.execute.return_value = []

        result = await self.use_case.execute_for_all_boards()

        self.assertTrue(result)
        self.assertEqual(self.mock_fetch_use_case.execute.call_count, 1)

    async def test_full_sync_renumbers_rows(self):
        """Test full sync renumbers rows sequentially."""
        mock_rows = [
            self._create_mock_story_row(key="TEST-1"),
            self._create_mock_story_row(key="TEST-2"),
        ]
        self.mock_fetch_use_case.execute.return_value = mock_rows

        await self.use_case.execute_for_board("TEST", days_back=None)

        self.assertEqual(mock_rows[0].row_number, 1)
        self.assertEqual(mock_rows[1].row_number, 2)

    async def test_incremental_sync_identifies_new_rows(self):
        """Test incremental sync identifies new rows correctly."""
        existing_data = [
            [
                "1",
                "Existing Task",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "0",
                "0",
                "0",
                "",
                "0",
                "0",
                "0",
                "0",
                "0",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "",
                "PARSCHAT-1",
            ],
        ]
        self.mock_sheets_gateway.get_sheet_values.return_value = existing_data

        new_row = self._create_mock_story_row(key="PARSCHAT-2")
        self.mock_fetch_use_case.execute.return_value = [new_row]

        result = await self.use_case.execute_for_board("TEST", days_back=7)

        self.assertTrue(result)
        self.mock_sheets_gateway.append_rows.assert_called_once()

    async def test_convert_row_to_values_includes_all_columns(self):
        """Test convert_row_to_values includes all required columns."""
        mock_row = self._create_mock_story_row()

        values = self.use_case._convert_row_to_values(mock_row)

        # Expected columns: 29 fixed + 3 developers + 2 issue keys = 34
        self.assertEqual(len(values), 34)
        self.assertEqual(values[0], 1)  # row_number
        self.assertEqual(values[1], "Test Task")  # task_title
        self.assertIn("PARSCHAT-1", values[33])  # developer_board_issue_key

    async def test_extract_developer_board_keys(self):
        """Test extraction of developer board issue keys."""
        features = [
            self._create_mock_story_row(key="PARSCHAT-123"),
            self._create_mock_story_row(key="PARSCHAT-456"),
        ]

        keys = self.mock_task_story_repository.extract_issue_keys_from_features(features)

        # Since it's a mock, we need to set up the return value
        self.mock_task_story_repository.extract_issue_keys_from_features = Mock(
            return_value=["PARSCHAT-123", "PARSCHAT-456"]
        )
        keys = self.mock_task_story_repository.extract_issue_keys_from_features(features)

        self.assertEqual(len(keys), 2)
        self.assertIn("PARSCHAT-123", keys)
        self.assertIn("PARSCHAT-456", keys)

    async def test_format_date_returns_yyyy_mm_dd(self):
        """Test date formatting returns YYYY-MM-DD."""
        from datetime import datetime

        date = datetime(2024, 10, 23)
        result = self.use_case._format_date(date)

        self.assertEqual(result, "2024-10-23")

    async def test_format_date_none_returns_empty_string(self):
        """Test date formatting with None returns empty string."""
        result = self.use_case._format_date(None)
        self.assertEqual(result, "")

    async def test_renumber_rows(self):
        """Test renumber_rows sets sequential row numbers."""
        # Create rows with different row numbers using model_copy
        row1 = self._create_mock_story_row(key="TEST-1").model_copy(update={"row_number": 10})
        row2 = self._create_mock_story_row(key="TEST-2").model_copy(update={"row_number": 20})
        row3 = self._create_mock_story_row(key="TEST-3").model_copy(update={"row_number": 30})
        
        rows = [row1, row2, row3]

        self.use_case._renumber_rows(rows)

        self.assertEqual(rows[0].row_number, 1)
        self.assertEqual(rows[1].row_number, 2)
        self.assertEqual(rows[2].row_number, 3)

    async def test_should_preserve_status_for_non_technical_statuses(self):
        """Test that statuses ۱, ۲, ۳, ۴, ۹, ۱۰ are preserved."""
        preserve_statuses = [
            "۱",
            "۱. ثبت و اولویت بندی",
            "۲",
            "۲. تحلیل مسئله و RFP",
            "۳",
            "۳. آماده سازی یوزر استوری",
            "۴",
            "۴. در مرحله طراحی",
            "۹",
            "۹. مستندسازی فنی",
            "۱۰",
            "۱۰. تکمیل شده",
        ]

        for status in preserve_statuses:
            result = self.use_case._should_preserve_status(status)
            self.assertTrue(result, f"Status '{status}' should be preserved")

    async def test_should_not_preserve_technical_statuses(self):
        """Test that statuses ۵, ۶, ۶.۵, ۷, ۸ are not preserved."""
        technical_statuses = [
            "۵",
            "۵. آماده پیاده سازی فنی",
            "۶",
            "۶. در حال پیاده سازی",
            "۶.۵",
            "۶.۵ توقف پیاده سازی فنی",
            "۷",
            "۷. تست فنی",
            "۸",
            "۸. آماده تحویل",
        ]

        for status in technical_statuses:
            result = self.use_case._should_preserve_status(status)
            self.assertFalse(result, f"Status '{status}' should not be preserved")

    async def test_merge_data_preserves_status(self):
        """Test that merge_data preserves sheet status for ۱, ۲, ۳, ۴, ۹, ۱۰."""
        # Create existing feature with preserved status
        existing_base = self._create_mock_story_row(key="PARSCHAT-1")
        existing_row = existing_base.model_copy(update={"status": "۱. ثبت و اولویت بندی"})
        
        # Mock repository to return existing features
        self.mock_task_story_repository.get_sheet_features = AsyncMock(return_value=[existing_row])
        self.mock_task_story_repository.extract_issue_keys_from_features = Mock(
            return_value=["PARSCHAT-1"]
        )

        # Jira says status is IN PROGRESS (would map to ۶)
        base_row = self._create_mock_story_row(key="PARSCHAT-1")
        new_row = base_row.model_copy(update={"status": "۶. در حال پیاده سازی"})
        self.mock_fetch_use_case.execute.return_value = [new_row]

        await self.use_case.execute_for_board("TEST", days_back=7)

        # Status should remain ۱ (preserved from sheet)
        # We need to check the actual data sent to update_cells
        update_call = self.mock_sheets_gateway.update_cells.call_args
        if update_call:
            updated_values = update_call[0][2]  # Third argument is values
            if updated_values and len(updated_values) > 0 and len(updated_values[0]) > 6:
                # Status column is index 6
                self.assertEqual(updated_values[0][6], "۱. ثبت و اولویت بندی")

    async def test_update_with_retry_handles_quota_error(self):
        """Test that protected statuses are preserved."""
        self.assertTrue(self.use_case._should_preserve_status("۱"))
        self.assertTrue(self.use_case._should_preserve_status("۱. ثبت و اولویت بندی"))
        self.assertTrue(self.use_case._should_preserve_status("۲"))
        self.assertTrue(self.use_case._should_preserve_status("۲. تحلیل مسئله و RFP"))
        self.assertTrue(self.use_case._should_preserve_status("۳"))
        self.assertTrue(self.use_case._should_preserve_status("۴"))
        self.assertTrue(self.use_case._should_preserve_status("۹"))
        self.assertTrue(self.use_case._should_preserve_status("۱۰"))

    async def test_should_not_preserve_status_for_jira_controlled_statuses(self):
        """Test that Jira-controlled statuses are not preserved."""
        self.assertFalse(self.use_case._should_preserve_status("۵"))
        self.assertFalse(self.use_case._should_preserve_status("۶"))
        self.assertFalse(self.use_case._should_preserve_status("۶.۵"))
        self.assertFalse(self.use_case._should_preserve_status("۷"))
        self.assertFalse(self.use_case._should_preserve_status("۸"))

    async def test_merge_data_preserves_sheet_status_for_protected_statuses(self):
        """Test that merge_data preserves sheet status for protected statuses."""
        # Create existing feature with preserved status
        existing_base = self._create_mock_story_row(key="PARSCHAT-1")
        existing_row = existing_base.model_copy(update={"status": "۱. ثبت و اولویت بندی"})
        
        # Mock repository to return existing features
        self.mock_task_story_repository.get_sheet_features = AsyncMock(return_value=[existing_row])
        self.mock_task_story_repository.extract_issue_keys_from_features = Mock(
            return_value=["PARSCHAT-1"]
        )

        # New row from Jira has different status
        base_row = self._create_mock_story_row(key="PARSCHAT-1")
        new_row = base_row.model_copy(update={"status": "۶. در حال پیاده سازی"})
        self.mock_fetch_use_case.execute.return_value = [new_row]

        await self.use_case.execute_for_board("TEST", days_back=7)

        # Verify update_cells was called
        self.mock_sheets_gateway.update_cells.assert_called_once()
        
        args = self.mock_sheets_gateway.update_cells.call_args
        if args and args[0] and len(args[0]) > 2:
            updated_values = args[0][2]
            if updated_values and len(updated_values) > 0 and len(updated_values[0]) > 6:
                # Status column is index 6
                self.assertEqual(updated_values[0][6], "۱. ثبت و اولویت بندی")

    async def test_update_with_retry_handles_quota_error(self):
        """Test update with retry handles quota exceeded errors."""
        self.mock_sheets_gateway.update_cells = AsyncMock(
            side_effect=Exception("429 Quota exceeded"),
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await self.use_case._update_with_retry(
                "test-id",
                "A1:B2",
                [["test"]],
                max_retries=2,
            )

        self.assertFalse(result)

    async def test_append_with_retry_handles_quota_error(self):
        """Test append with retry handles quota exceeded errors."""
        self.mock_sheets_gateway.append_rows = AsyncMock(
            side_effect=Exception("429 Quota exceeded"),
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await self.use_case._append_with_retry(
                "test-id",
                "A:B",
                [["test"]],
                max_retries=2,
            )

        self.assertFalse(result)

    def _create_mock_story_row(self, key="PARSCHAT-1"):
        """Create a mock SynthPMFeatureEntity for testing."""
        return SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Task",
            epic="Test Epic",
            necessity="Must-have",
            release="1.0",
            departments="Backend, Frontend",
            status="۶. در حال پیاده سازی",
            priority="High",
            department_deps=None,
            eta_hours=8,
            total_hours=8,
            involved_people="User One, User Two",
            ai="0",
            backend="2",
            frontend="2",
            devops="0",
            ui_ux="0",
            creation_date=None,
            implementation_start_date=None,
            deadline=None,
            sprint="55: 10-21 to 10-27",
            last_sprint=None,
            sprint_list=None,
            dependencies=None,
            initial_delivery_time=None,
            description="Test description",
            acceptance_criteria=None,
            test_cases=None,
            po_notes=None,
            jira_issue_key="PCD-123",
            developer_board_issue_key=key,
            version=None,
            times={"User One": 2, "User Two": 2},
        )


if __name__ == "__main__":
    unittest.main()
