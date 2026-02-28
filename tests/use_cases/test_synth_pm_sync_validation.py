"""Tests for SynthPM sync validation — verifying that existing tasks use relaxed
validation while new task creation uses strict validation.

The critical bug fix: features with existing developer_board_issue_key that have
cleared sprints/dates must still pass validation (via validate_feature_for_update)
so that the clearing propagates to Jira. Only brand-new tasks require strict
validation (via validate_feature_for_task_creation).
"""
import logging
import logging.handlers
import os
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

os.makedirs("/tmp/jira_test_logs", exist_ok=True)
_orig_rfh_init = logging.handlers.RotatingFileHandler.__init__


def _patched_rfh_init(self, filename, *args, **kwargs):
    if "logs/logs.log" in str(filename):
        filename = "/tmp/jira_test_logs/logs.log"
    _orig_rfh_init(self, filename, *args, **kwargs)


logging.handlers.RotatingFileHandler.__init__ = _patched_rfh_init

from jira_telegram_bot.entities.synth_pm.constants import StatusDescriptions
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


def _make_feature(
    row_number: int = 1,
    sheet_row_number: int = 2,
    task_title: str = "Test Task",
    status: str = "۶. در حال پیاده سازی",
    sprint_list: Optional[List[str]] = None,
    sprint: Optional[str] = None,
    developer_board_issue_key: Optional[str] = None,
    jira_issue_key: Optional[str] = None,
    involved_people: Optional[str] = "Ali",
    ai: Optional[str] = "Ali",
    release: Optional[str] = None,
    story_name: Optional[str] = None,
) -> SynthPMFeatureEntity:
    """Create a test SynthPMFeatureEntity.

    Args:
        row_number: Row number in table.
        sheet_row_number: Row number in sheet.
        task_title: Task title.
        status: Feature status.
        sprint_list: List of sprint names.
        sprint: Sprint name.
        developer_board_issue_key: Existing developer board issue key.
        jira_issue_key: Existing PM board issue key.
        involved_people: Involved people string.
        ai: AI department person.
        release: Release version.
        story_name: Story/feature group name.

    Returns:
        Configured SynthPMFeatureEntity.
    """
    return SynthPMFeatureEntity(
        row_number=row_number,
        sheet_row_number=sheet_row_number,
        task_title=task_title,
        status=status,
        sprint_list=sprint_list,
        sprint=sprint,
        developer_board_issue_key=developer_board_issue_key,
        jira_issue_key=jira_issue_key,
        involved_people=involved_people,
        ai=ai,
        release=release,
        story_name=story_name,
    )


def _make_sync_results() -> Dict[str, Any]:
    """Create a fresh sync_results dictionary.

    Returns:
        Dictionary with all required sync result keys.
    """
    return {
        "skipped": [],
        "errors": [],
        "created_jira_tasks": 0,
        "created_developer_board_tasks": 0,
        "updated_jira_tasks": 0,
        "updated_developer_board_tasks": 0,
        "converted_to_subtasks": 0,
    }


def _make_project_config_mock() -> MagicMock:
    """Create a mock project_config with sync_settings.

    Returns:
        MagicMock with minimum_status_for_task_creation configured.
    """
    config = MagicMock()
    config.sync_settings.minimum_status_for_task_creation = "۵. آماده پیاده سازی فنی"
    return config


def _make_use_case() -> SynthPMUseCase:
    """Create a SynthPMUseCase with mocked dependencies.

    Returns:
        Configured SynthPMUseCase instance with mocks.
    """
    mock_repo = MagicMock()
    mock_repo.project_config = _make_project_config_mock()
    mock_repo.validate_feature_for_task_creation = MagicMock(
        return_value=(True, None),
    )
    mock_repo.validate_feature_for_update = MagicMock(
        return_value=(True, None),
    )
    mock_repo.get_story_by_release_name = AsyncMock(return_value=None)
    mock_repo.create_release_story = AsyncMock(return_value="PARSCHAT-100")
    mock_repo.update_developer_board_task_from_feature = AsyncMock(return_value=True)
    mock_repo.create_developer_board_task_from_feature = AsyncMock(
        return_value="PARSCHAT-200",
    )
    mock_repo.create_developer_board_subtask = AsyncMock(
        return_value="PARSCHAT-201",
    )
    mock_repo.update_developer_board_feature = AsyncMock(return_value=True)
    mock_repo.update_jira_task_from_feature = AsyncMock(return_value=True)
    mock_repo.create_jira_task_from_feature = AsyncMock(return_value="PCD-300")
    mock_repo.convert_existing_task_to_subtask = AsyncMock(return_value="PARSCHAT-200")
    mock_repo.update_story_from_subtasks = AsyncMock(return_value=True)
    mock_repo.jira_repository = MagicMock()
    mock_repo._build_story_description = MagicMock(return_value="desc")

    mock_settings = MagicMock()
    mock_user_config = MagicMock()
    mock_notification = MagicMock()
    mock_ac_use_case = MagicMock()
    mock_ts_use_case = MagicMock()

    use_case = SynthPMUseCase(
        repository=mock_repo,
        settings=mock_settings,
        user_config=mock_user_config,
        notification_gateway=mock_notification,
        generate_acceptance_criteria_use_case=mock_ac_use_case,
        generate_test_scenarios_use_case=mock_ts_use_case,
    )
    return use_case


class TestCreateReleaseStoryValidation(unittest.IsolatedAsyncioTestCase):
    """Tests for _create_release_story_with_subtasks validation path."""

    async def test_a_existing_task_uses_relaxed_validation(self):
        """Feature with existing developer_board_issue_key uses validate_feature_for_update."""
        use_case = _make_use_case()
        feature = _make_feature(
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
            sprint=None,
        )
        sync_results = _make_sync_results()

        await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        use_case.repository.validate_feature_for_update.assert_called_once_with(
            feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        use_case.repository.validate_feature_for_task_creation.assert_not_called()

    async def test_a_new_task_uses_strict_validation(self):
        """Feature without developer_board_issue_key uses validate_feature_for_task_creation."""
        use_case = _make_use_case()
        feature = _make_feature(
            developer_board_issue_key=None,
            sprint_list=["Sprint 10"],
            sprint="Sprint 10",
        )
        sync_results = _make_sync_results()

        await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        use_case.repository.validate_feature_for_task_creation.assert_called_once_with(
            feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        use_case.repository.validate_feature_for_update.assert_not_called()

    async def test_a_mixed_features_use_correct_validators(self):
        """Mix of new and existing features each use the correct validator."""
        use_case = _make_use_case()

        existing_feature = _make_feature(
            row_number=1,
            sheet_row_number=2,
            task_title="Existing Task",
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
        )
        new_feature = _make_feature(
            row_number=2,
            sheet_row_number=3,
            task_title="New Task",
            developer_board_issue_key=None,
            sprint_list=["Sprint 10"],
        )
        sync_results = _make_sync_results()

        await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[existing_feature, new_feature],
            sync_results=sync_results,
        )

        use_case.repository.validate_feature_for_update.assert_called_once_with(
            existing_feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        use_case.repository.validate_feature_for_task_creation.assert_called_once_with(
            new_feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )

    async def test_a_existing_task_cleared_sprint_still_passes(self):
        """Feature with existing key and no sprint should pass relaxed validation."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_update.return_value = (True, None)

        feature = _make_feature(
            developer_board_issue_key="PARSCHAT-500",
            jira_issue_key="PCD-400",
            sprint_list=None,
            sprint=None,
        )
        sync_results = _make_sync_results()

        await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        self.assertEqual(len(sync_results["skipped"]), 0)

    async def test_a_new_task_no_sprint_fails_strict_validation(self):
        """New feature without sprint fails strict validation and is skipped."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_task_creation.return_value = (
            False,
            "Row 2 ('New Task'): No sprint defined",
        )

        feature = _make_feature(
            developer_board_issue_key=None,
            sprint_list=None,
            sprint=None,
        )
        sync_results = _make_sync_results()

        result = await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        self.assertIsNone(result)
        self.assertEqual(len(sync_results["skipped"]), 1)
        self.assertIn("No sprint defined", sync_results["skipped"][0])

    async def test_a_all_features_invalid_returns_none(self):
        """When all features fail validation, returns None."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_task_creation.return_value = (
            False,
            "Row 2: Invalid",
        )

        feature = _make_feature(developer_board_issue_key=None)
        sync_results = _make_sync_results()

        result = await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        self.assertIsNone(result)

    async def test_a_existing_feature_update_called_after_validation(self):
        """After passing relaxed validation, existing feature reaches update path."""
        use_case = _make_use_case()
        feature = _make_feature(
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
            sprint=None,
            status="۶. در حال پیاده سازی",
        )
        sync_results = _make_sync_results()

        await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        use_case.repository.update_developer_board_task_from_feature.assert_called_once()


class TestProcessFeatureValidation(unittest.IsolatedAsyncioTestCase):
    """Tests for _process_feature validation path."""

    async def test_a_existing_both_keys_uses_relaxed_validation(self):
        """Feature with both jira_issue_key and developer_board_issue_key uses relaxed validation."""
        use_case = _make_use_case()
        feature = _make_feature(
            jira_issue_key="PCD-400",
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
            sprint=None,
            status="۶. در حال پیاده سازی",
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        use_case.repository.validate_feature_for_update.assert_called_once_with(
            feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        use_case.repository.validate_feature_for_task_creation.assert_not_called()

    async def test_a_new_feature_no_keys_uses_strict_validation(self):
        """Feature without keys uses strict validation."""
        use_case = _make_use_case()
        feature = _make_feature(
            jira_issue_key=None,
            developer_board_issue_key=None,
            sprint_list=["Sprint 10"],
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        use_case.repository.validate_feature_for_task_creation.assert_called_once_with(
            feature,
            minimum_status="۵. آماده پیاده سازی فنی",
        )
        use_case.repository.validate_feature_for_update.assert_not_called()

    async def test_a_only_jira_key_uses_strict_validation(self):
        """Feature with only jira_issue_key but no developer_board_issue_key uses strict."""
        use_case = _make_use_case()
        feature = _make_feature(
            jira_issue_key="PCD-400",
            developer_board_issue_key=None,
            sprint_list=["Sprint 10"],
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        use_case.repository.validate_feature_for_task_creation.assert_called_once()
        use_case.repository.validate_feature_for_update.assert_not_called()

    async def test_a_existing_feature_cleared_sprint_reaches_update(self):
        """Feature with both keys and cleared sprint reaches the update path."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_update.return_value = (True, None)

        feature = _make_feature(
            jira_issue_key="PCD-400",
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
            sprint=None,
            status="۶. در حال پیاده سازی",
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        use_case.repository.update_jira_task_from_feature.assert_called_once()
        use_case.repository.update_developer_board_task_from_feature.assert_called_once()
        self.assertEqual(len(sync_results["skipped"]), 0)

    async def test_a_existing_feature_failed_update_validation_skipped(self):
        """Feature with both keys that fails even relaxed validation is skipped."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_update.return_value = (
            False,
            "Row 2 ('Test Task'): Status below minimum",
        )

        feature = _make_feature(
            jira_issue_key="PCD-400",
            developer_board_issue_key="PARSCHAT-500",
            status="۱. ثبت و اولویت بندی",
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        self.assertEqual(len(sync_results["skipped"]), 1)
        use_case.repository.update_developer_board_task_from_feature.assert_not_called()

    async def test_a_empty_title_skipped_before_validation(self):
        """Feature with empty title is skipped before any validation."""
        use_case = _make_use_case()
        feature = _make_feature(task_title="", developer_board_issue_key="PARSCHAT-500")
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        use_case.repository.validate_feature_for_update.assert_not_called()
        use_case.repository.validate_feature_for_task_creation.assert_not_called()


class TestValidateFeatureForUpdate(unittest.TestCase):
    """Tests for the validate_feature_for_update method on the repository."""

    def setUp(self):
        """Set up test fixtures."""
        from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
            SynthPMRepository,
        )
        self.repo = SynthPMRepository.__new__(SynthPMRepository)
        self.repo.project_config = _make_project_config_mock()

    def test_valid_feature_no_sprint(self):
        """Feature with valid title and status but no sprint passes."""
        feature = _make_feature(
            status="۶. در حال پیاده سازی",
            sprint_list=None,
            sprint=None,
            involved_people=None,
        )
        is_valid, error = self.repo.validate_feature_for_update(feature)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_feature_no_dates(self):
        """Feature with valid title and status but no dates passes."""
        feature = _make_feature(
            status="۵. آماده پیاده سازی فنی",
            sprint_list=None,
            sprint=None,
        )
        is_valid, error = self.repo.validate_feature_for_update(feature)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_empty_title_fails(self):
        """Feature with empty title fails update validation."""
        feature = _make_feature(task_title="", status="۶. در حال پیاده سازی")
        is_valid, error = self.repo.validate_feature_for_update(feature)
        self.assertFalse(is_valid)
        self.assertIn("Task title is empty", error)

    def test_whitespace_title_fails(self):
        """Feature with whitespace-only title fails update validation."""
        feature = _make_feature(task_title="   ", status="۶. در حال پیاده سازی")
        is_valid, error = self.repo.validate_feature_for_update(feature)
        self.assertFalse(is_valid)
        self.assertIn("Task title is empty", error)

    def test_status_below_minimum_fails(self):
        """Feature with status below minimum fails update validation."""
        feature = _make_feature(status="۱. ثبت و اولویت بندی")
        is_valid, error = self.repo.validate_feature_for_update(feature)
        self.assertFalse(is_valid)
        self.assertIn("below minimum", error)

    def test_custom_minimum_status(self):
        """Custom minimum_status parameter is respected."""
        feature = _make_feature(status="۴. در مرحله طراحی")
        is_valid, error = self.repo.validate_feature_for_update(
            feature, minimum_status="۴. در مرحله طراحی",
        )
        self.assertTrue(is_valid)

    def test_completed_status_passes(self):
        """Feature with completed status passes update validation."""
        feature = _make_feature(status="۱۰. تکمیل شده")
        is_valid, error = self.repo.validate_feature_for_update(feature)
        self.assertTrue(is_valid)
        self.assertIsNone(error)


class TestValidateFeatureForTaskCreation(unittest.TestCase):
    """Tests for validate_feature_for_task_creation — strict validation."""

    def setUp(self):
        """Set up test fixtures."""
        from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
            SynthPMRepository,
        )
        self.repo = SynthPMRepository.__new__(SynthPMRepository)
        self.repo.project_config = _make_project_config_mock()

    def test_valid_feature_all_fields(self):
        """Feature with all required fields passes strict validation."""
        feature = _make_feature(
            status="۶. در حال پیاده سازی",
            sprint_list=["Sprint 10"],
            sprint="Sprint 10",
            involved_people="Ali",
            ai="Ali",
        )
        self.repo.extract_dates_from_feature_in_str = MagicMock(
            return_value={"target_start": "2025-01-01", "target_end": None, "due_date": None},
        )
        is_valid, error = self.repo.validate_feature_for_task_creation(feature)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_no_sprint_fails(self):
        """Feature without sprint fails strict validation."""
        feature = _make_feature(
            status="۶. در حال پیاده سازی",
            sprint_list=None,
            sprint=None,
            involved_people="Ali",
            ai="Ali",
        )
        is_valid, error = self.repo.validate_feature_for_task_creation(feature)
        self.assertFalse(is_valid)
        self.assertIn("No sprint defined", error)

    def test_no_involved_people_fails(self):
        """Feature without involved people fails strict validation."""
        feature = _make_feature(
            status="۶. در حال پیاده سازی",
            sprint_list=["Sprint 10"],
            involved_people=None,
            ai="Ali",
        )
        is_valid, error = self.repo.validate_feature_for_task_creation(feature)
        self.assertFalse(is_valid)
        self.assertIn("No assignees", error)

    def test_status_below_minimum_fails(self):
        """Feature with low status fails strict validation."""
        feature = _make_feature(
            status="۱. ثبت و اولویت بندی",
            sprint_list=["Sprint 10"],
        )
        is_valid, error = self.repo.validate_feature_for_task_creation(feature)
        self.assertFalse(is_valid)
        self.assertIn("below minimum", error)

    def test_empty_title_fails(self):
        """Feature with empty title fails strict validation."""
        feature = _make_feature(
            task_title="",
            sprint_list=["Sprint 10"],
        )
        is_valid, error = self.repo.validate_feature_for_task_creation(feature)
        self.assertFalse(is_valid)
        self.assertIn("Task title is empty", error)


class TestCreateRegularTasksValidation(unittest.IsolatedAsyncioTestCase):
    """Tests for _create_regular_tasks_for_features handling existing vs new tasks."""

    async def test_a_existing_task_gets_updated(self):
        """Feature with existing developer_board_issue_key triggers update, not create."""
        use_case = _make_use_case()
        feature = _make_feature(
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
            status="۶. در حال پیاده سازی",
        )
        sync_results = _make_sync_results()

        await use_case._create_regular_tasks_for_features([feature], sync_results)

        use_case.repository.update_developer_board_task_from_feature.assert_called_once()
        use_case.repository.create_developer_board_task_from_feature.assert_not_called()

    async def test_a_existing_task_completed_status_skipped(self):
        """Feature with completed status is skipped for updates."""
        use_case = _make_use_case()
        feature = _make_feature(
            developer_board_issue_key="PARSCHAT-500",
            status=StatusDescriptions.COMPLETED.value,
        )
        sync_results = _make_sync_results()

        await use_case._create_regular_tasks_for_features([feature], sync_results)

        use_case.repository.update_developer_board_task_from_feature.assert_not_called()


class TestEndToEndSprintClearing(unittest.IsolatedAsyncioTestCase):
    """End-to-end tests verifying the sprint-clearing scenario."""

    async def test_a_feature_with_cleared_sprint_reaches_update_via_release_story(self):
        """Feature that had sprint cleared in sheet passes through validation and reaches update."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_update.return_value = (True, None)

        feature = _make_feature(
            developer_board_issue_key="PARSCHAT-500",
            jira_issue_key="PCD-400",
            sprint_list=None,
            sprint=None,
            status="۶. در حال پیاده سازی",
            involved_people="Ali",
            ai="Ali",
        )
        sync_results = _make_sync_results()

        await use_case._create_release_story_with_subtasks(
            release_name="No Release",
            features=[feature],
            sync_results=sync_results,
        )

        self.assertEqual(len(sync_results["skipped"]), 0)
        use_case.repository.update_developer_board_task_from_feature.assert_called_once()

    async def test_a_feature_with_cleared_sprint_reaches_update_via_process(self):
        """Feature with cleared sprint passes _process_feature validation."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_update.return_value = (True, None)

        feature = _make_feature(
            jira_issue_key="PCD-400",
            developer_board_issue_key="PARSCHAT-500",
            sprint_list=None,
            sprint=None,
            status="۶. در حال پیاده سازی",
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        self.assertEqual(len(sync_results["skipped"]), 0)
        use_case.repository.update_jira_task_from_feature.assert_called_once()
        use_case.repository.update_developer_board_task_from_feature.assert_called_once()

    async def test_a_new_feature_without_sprint_blocked_correctly(self):
        """New feature without sprint is correctly blocked from creation."""
        use_case = _make_use_case()
        use_case.repository.validate_feature_for_task_creation.return_value = (
            False,
            "Row 2 ('New'): No sprint defined",
        )

        feature = _make_feature(
            jira_issue_key=None,
            developer_board_issue_key=None,
            sprint_list=None,
            sprint=None,
        )
        sync_results = _make_sync_results()

        await use_case._process_feature(feature, sync_results)

        self.assertEqual(len(sync_results["skipped"]), 1)
        use_case.repository.create_jira_task_from_feature.assert_not_called()
        use_case.repository.create_developer_board_task_from_feature.assert_not_called()


if __name__ == "__main__":
    unittest.main()
