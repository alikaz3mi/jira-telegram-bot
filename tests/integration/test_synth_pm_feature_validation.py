"""Integration tests for SynthPM feature processing and validation."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


class TestSynthPMFeatureProcessingIntegration(unittest.TestCase):
    """Integration tests for feature processing with validation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mocks
        self.repository = MagicMock()
        self.settings = MagicMock()
        self.user_config = MagicMock()
        self.notification_gateway = MagicMock()
        self.generate_acceptance_criteria_use_case = MagicMock()
        self.generate_test_scenarios_use_case = MagicMock()
        
        # Setup project config
        self.project_config = MagicMock()
        self.project_config.sync_settings.minimum_status_for_task_creation = (
            "۵. آماده پیاده سازی فنی"
        )
        self.repository.project_config = self.project_config
        
        # Create use case
        self.use_case = SynthPMUseCase(
            repository=self.repository,
            settings=self.settings,
            user_config=self.user_config,
            notification_gateway=self.notification_gateway,
            generate_acceptance_criteria_use_case=self.generate_acceptance_criteria_use_case,
            generate_test_scenarios_use_case=self.generate_test_scenarios_use_case,
        )

    async def test_process_feature_skips_empty_row(self):
        """Test that empty rows are skipped without error."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            task_title="",  # Empty
        )
        
        sync_results = {
            "created_jira_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        await self.use_case._process_feature(feature, sync_results)
        
        # Should not create any tasks
        self.assertEqual(sync_results["created_jira_tasks"], 0)
        self.assertEqual(len(sync_results["errors"]), 0)
        # Empty rows are logged as debug, not added to skipped
        self.assertEqual(len(sync_results["skipped"]), 0)

    async def test_process_feature_skips_low_status(self):
        """Test that features with low status are skipped."""
        feature = SynthPMFeatureEntity(
            row_number=5,
            task_title="Early Stage Feature",
            status="۲. تحلیل مسئله و RFP",  # Below minimum
            involved_people="User1",
            sprint="Sprint-1",
            ai=True,
            implementation_start_date="2024-01-01",
        )
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (
            False,
            "Row 5: Status below minimum",
        )
        
        sync_results = {
            "created_jira_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        await self.use_case._process_feature(feature, sync_results)
        
        self.assertEqual(sync_results["created_jira_tasks"], 0)
        self.assertEqual(len(sync_results["skipped"]), 1)
        self.assertIn("below minimum", sync_results["skipped"][0])

    async def test_process_feature_skips_missing_assignees(self):
        """Test that features without assignees are skipped."""
        feature = SynthPMFeatureEntity(
            row_number=10,
            task_title="Unassigned Feature",
            status="۶. در حال پیاده سازی",
            involved_people="",  # Empty
            sprint="Sprint-1",
            ai=True,
            implementation_start_date="2024-01-01",
        )
        
        self.repository.validate_feature_for_task_creation.return_value = (
            False,
            "Row 10: No assignees defined",
        )
        
        sync_results = {
            "created_jira_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        await self.use_case._process_feature(feature, sync_results)
        
        self.assertEqual(len(sync_results["skipped"]), 1)
        self.assertIn("assignees", sync_results["skipped"][0].lower())

    async def test_process_feature_creates_task_when_valid(self):
        """Test that valid features create tasks successfully."""
        feature = SynthPMFeatureEntity(
            row_number=15,
            task_title="Valid Feature",
            status="۶. در حال پیاده سازی",
            involved_people="User1, User2",
            sprint="Sprint-1",
            ai=True,
            backend=True,
            implementation_start_date="2024-01-01",
            deadline="2024-01-31",
            jira_issue_key=None,  # No task created yet
        )
        
        # Mock validation passes
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock task creation
        self.repository.create_jira_task_from_feature = AsyncMock(
            return_value="PROJ-123"
        )
        
        sync_results = {
            "created_jira_tasks": 0,
            "updated_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        await self.use_case._process_feature(feature, sync_results)
        
        # Should create PM task
        self.assertEqual(sync_results["created_jira_tasks"], 1)
        self.assertEqual(len(sync_results["skipped"]), 0)
        self.assertEqual(len(sync_results["errors"]), 0)
        self.repository.create_jira_task_from_feature.assert_called_once()

    async def test_process_feature_handles_multiple_validation_failures(self):
        """Test processing multiple features with different validation failures."""
        features = [
            SynthPMFeatureEntity(
                row_number=1,
                task_title="Feature 1",
                status="۱. ثبت و اولویت بندی",  # Low status
                involved_people="User1",
                sprint="Sprint-1",
                ai=True,
                implementation_start_date="2024-01-01",
            ),
            SynthPMFeatureEntity(
                row_number=2,
                task_title="Feature 2",
                status="۶. در حال پیاده سازی",
                involved_people="",  # No assignees
                sprint="Sprint-1",
                ai=True,
                implementation_start_date="2024-01-01",
            ),
            SynthPMFeatureEntity(
                row_number=3,
                task_title="Feature 3",
                status="۶. در حال پیاده سازی",
                involved_people="User1",
                sprint="",  # No sprint
                ai=True,
                implementation_start_date="2024-01-01",
            ),
        ]
        
        # Mock validation to fail for each feature
        self.repository.validate_feature_for_task_creation.side_effect = [
            (False, "Row 1: Status below minimum"),
            (False, "Row 2: No assignees"),
            (False, "Row 3: No sprint"),
        ]
        
        sync_results = {
            "created_jira_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        for feature in features:
            await self.use_case._process_feature(feature, sync_results)
        
        self.assertEqual(sync_results["created_jira_tasks"], 0)
        self.assertEqual(len(sync_results["skipped"]), 3)
        self.assertIn("status", sync_results["skipped"][0].lower())
        self.assertIn("assignees", sync_results["skipped"][1].lower())
        self.assertIn("sprint", sync_results["skipped"][2].lower())

    async def test_sync_includes_skipped_in_results(self):
        """Test that sync results include skipped items summary."""
        # Mock get features
        features = [
            SynthPMFeatureEntity(
                row_number=1,
                task_title="Valid Feature",
                status="۶. در حال پیاده سازی",
                involved_people="User1",
                sprint="Sprint-1",
                ai=True,
                implementation_start_date="2024-01-01",
                jira_issue_key="PROJ-1",
                developer_board_issue_key="DEV-1",
            ),
            SynthPMFeatureEntity(
                row_number=2,
                task_title="Invalid Feature",
                status="۲. تحلیل مسئله و RFP",
                involved_people="User1",
                sprint="Sprint-1",
                ai=True,
                implementation_start_date="2024-01-01",
            ),
        ]
        
        self.repository.get_developer_board_features = AsyncMock(return_value=features)
        self.repository.get_change_tracker = AsyncMock(return_value=Mock(snapshots={}))
        self.repository.update_change_tracker = AsyncMock()
        self.repository.update_sync_status = AsyncMock()
        
        # Mock validation
        def mock_validate(feature, minimum_status=None):
            if feature.row_number == 2:
                return False, "Row 2: Status below minimum"
            return True, None
        
        self.repository.validate_feature_for_task_creation.side_effect = mock_validate
        
        # Run sync
        result = await self.use_case.sync_developer_board_features()
        
        self.assertEqual(result["status"], "success")
        self.assertIn("skipped", result["results"])
        self.assertEqual(len(result["results"]["skipped"]), 1)


def async_test(coro):
    """Decorator to run async tests."""
    import asyncio
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# Apply async decorator
for name in dir(TestSynthPMFeatureProcessingIntegration):
    if name.startswith('test_'):
        method = getattr(TestSynthPMFeatureProcessingIntegration, name)
        import asyncio
        if asyncio.iscoroutinefunction(method):
            setattr(TestSynthPMFeatureProcessingIntegration, name, async_test(method))


if __name__ == "__main__":
    unittest.main()
