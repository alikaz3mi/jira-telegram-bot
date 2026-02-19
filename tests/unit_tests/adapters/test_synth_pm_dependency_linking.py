"""Unit tests for SynthPM PM Board dependency linking.

Verifies that create_jira_task_from_feature and update_jira_task_from_feature
correctly invoke _link_dependencies_by_summary for PM Board tasks.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity


def _make_feature(**overrides) -> SynthPMFeatureEntity:
    """Create a SynthPMFeatureEntity with sensible defaults.

    Args:
        **overrides: Field overrides for the entity.

    Returns:
        A SynthPMFeatureEntity instance.
    """
    defaults = {
        "row_number": 1,
        "sheet_row_number": 2,
        "task_title": "Sample Feature",
        "status": "In Progress",
        "priority": "High",
        "total_hours": 8.0,
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)


def _make_mock_issue(key: str = "PM-10") -> MagicMock:
    """Create a properly configured mock Jira issue.

    Args:
        key: The issue key.

    Returns:
        A MagicMock configured to act like a Jira issue.
    """
    mock_issue = MagicMock()
    mock_issue.key = key
    mock_issue.fields = MagicMock()
    mock_issue.fields.summary = "Sample Feature"
    mock_issue.fields.description = "desc"
    mock_issue.fields.priority = MagicMock()
    mock_issue.fields.priority.name = "High"
    mock_issue.fields.fixVersions = []
    mock_issue.fields.status = MagicMock()
    mock_issue.fields.status.name = "In Progress"
    mock_issue.fields.duedate = None
    mock_issue.fields.components = []
    mock_issue.fields.labels = ["user1"]
    mock_issue.fields.issuetype = MagicMock()
    mock_issue.fields.issuetype.name = "Task"
    mock_issue.fields.timetracking = None
    mock_issue.fields.assignee = MagicMock()
    mock_issue.fields.assignee.name = "dev_user"
    mock_issue.fields.subtasks = []

    fields_dict = {
        "customfield_10100": None,
        "customfield_10101": None,
        "customfield_10102": None,
    }

    original_getattr = type(mock_issue.fields).__getattr__

    def custom_getattr(self_fields, name):
        if name in fields_dict:
            return fields_dict[name]
        return original_getattr(self_fields, name)

    mock_issue.fields.__dict__.update(fields_dict)

    return mock_issue


def _make_repository() -> tuple:
    """Create a SynthPMRepository with all dependencies mocked.

    Returns:
        Tuple of (repository, jira_repository_mock, user_config_mock).
    """
    google_sheet_client = AsyncMock()
    jira_repository = MagicMock()
    user_config = MagicMock()

    settings = MagicMock()
    project_config = MagicMock()
    project_config.project_key = "TEST"
    project_config.boards.developer_board.jira_board_key = "DEV"
    project_config.boards.pm_board.jira_board_key = "PM"
    project_config.boards.pm_board.enabled = True
    project_config.boards.pm_board.sheet_name = "Features"
    project_config.boards.pm_board.data_range = "A1:Z100"
    project_config.spreadsheet_id = "spreadsheet_id"

    settings.get_project_config = MagicMock(return_value=project_config)
    settings.get_project_metadata = MagicMock(return_value=MagicMock())

    jira_repository.get_board_id = MagicMock(return_value=123)
    jira_repository.jira_target_start_id = "customfield_10100"
    jira_repository.jira_target_end_id = "customfield_10101"
    jira_repository.jira_sprint_id = "customfield_10102"

    mock_created_issue = MagicMock()
    mock_created_issue.key = "PM-10"
    jira_repository.create_task = MagicMock(return_value=mock_created_issue)
    jira_repository.get_issue_url = MagicMock(
        return_value="http://jira.example.com/PM-10",
    )
    jira_repository.release_exist = MagicMock(return_value=True)
    jira_repository.get_issue_spent_time_in_seconds = MagicMock(return_value=0)

    repository = SynthPMRepository(
        google_sheet_client=google_sheet_client,
        jira_repository=jira_repository,
        settings=settings,
        user_config=user_config,
    )

    return repository, jira_repository, user_config


class TestPMBoardDependencyLinkingOnCreate(unittest.IsolatedAsyncioTestCase):
    """Test that create_jira_task_from_feature links dependencies."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.repository, self.jira_repository, self.user_config = _make_repository()

    async def test_create_calls_link_dependencies_with_correct_args(self):
        """Verify _link_dependencies_by_summary is called after PM task creation."""
        feature = _make_feature(dependencies="Login Page, Dashboard")

        with patch.object(
            self.repository, "_link_dependencies_by_summary", return_value=2,
        ) as mock_link, patch.object(
            self.repository, "_transition_issue_to_status",
        ), patch.object(
            self.repository, "_determine_jira_status", return_value="In Progress",
        ), patch.object(
            self.repository, "_create_release_not_exist",
        ), patch.object(
            self.repository, "_map_priority", return_value="High",
        ), patch.object(
            self.repository, "_map_components", return_value=[],
        ), patch.object(
            self.repository, "update_developer_board_feature", new_callable=AsyncMock,
        ):
            result = await self.repository.create_jira_task_from_feature(feature)

            self.assertEqual(result, "PM-10")
            mock_link.assert_called_once_with(
                "PM-10",
                feature,
                self.repository.pm_project_key,
            )

    async def test_create_succeeds_when_no_dependencies(self):
        """Verify create succeeds and skips linking when dependencies field is empty."""
        feature = _make_feature(dependencies=None)

        with patch.object(
            self.repository, "_link_dependencies_by_summary", return_value=0,
        ) as mock_link, patch.object(
            self.repository, "_transition_issue_to_status",
        ), patch.object(
            self.repository, "_determine_jira_status", return_value="To Do",
        ), patch.object(
            self.repository, "_create_release_not_exist",
        ), patch.object(
            self.repository, "_map_priority", return_value="Medium",
        ), patch.object(
            self.repository, "_map_components", return_value=[],
        ), patch.object(
            self.repository, "update_developer_board_feature", new_callable=AsyncMock,
        ):
            result = await self.repository.create_jira_task_from_feature(feature)

            self.assertEqual(result, "PM-10")
            mock_link.assert_called_once()

    async def test_create_continues_when_dependency_linking_fails(self):
        """Verify task creation still succeeds if dependency linking throws."""
        feature = _make_feature(dependencies="Non-existent Task")

        with patch.object(
            self.repository, "_link_dependencies_by_summary",
            side_effect=Exception("Jira link error"),
        ), patch.object(
            self.repository, "_transition_issue_to_status",
        ), patch.object(
            self.repository, "_determine_jira_status", return_value="To Do",
        ), patch.object(
            self.repository, "_create_release_not_exist",
        ), patch.object(
            self.repository, "_map_priority", return_value="Medium",
        ), patch.object(
            self.repository, "_map_components", return_value=[],
        ), patch.object(
            self.repository, "update_developer_board_feature", new_callable=AsyncMock,
        ):
            result = await self.repository.create_jira_task_from_feature(feature)

            self.assertEqual(result, "PM-10")


class TestPMBoardDependencyLinkingOnUpdate(unittest.IsolatedAsyncioTestCase):
    """Test that update_jira_task_from_feature links dependencies."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.repository, self.jira_repository, self.user_config = _make_repository()
        self.mock_pm_issue = _make_mock_issue("PM-10")
        self.mock_dev_issue = _make_mock_issue("DEV-5")

    def _setup_issue_mocks(self):
        """Configure get_issue and user config for update tests."""
        self.jira_repository.get_issue = MagicMock(
            side_effect=[self.mock_pm_issue, self.mock_dev_issue],
        )
        mock_user_cfg = MagicMock()
        mock_user_cfg.google_sheet_name = "user1"
        self.user_config.get_user_config_by_jira_username = MagicMock(
            return_value=mock_user_cfg,
        )

    async def test_update_calls_link_dependencies_with_correct_args(self):
        """Verify _link_dependencies_by_summary is called during PM task update."""
        feature = _make_feature(
            jira_issue_key="PM-10",
            dependencies="Login Page, Dashboard",
            involved_people="user1",
        )
        self._setup_issue_mocks()

        with patch.object(
            self.repository, "_link_dependencies_by_summary", return_value=2,
        ) as mock_link, patch.object(
            self.repository, "_determine_jira_status", return_value="In Progress",
        ), patch.object(
            self.repository, "_transition_issue_to_status",
        ), patch.object(
            self.repository, "_map_components", return_value=[],
        ):
            result = await self.repository.update_jira_task_from_feature(feature)

            self.assertTrue(result)
            mock_link.assert_called_once_with(
                "PM-10",
                feature,
                self.repository.pm_project_key,
            )

    async def test_update_succeeds_when_no_dependencies(self):
        """Verify update works correctly with empty dependencies."""
        feature = _make_feature(
            jira_issue_key="PM-10",
            dependencies=None,
            involved_people="user1",
        )
        self._setup_issue_mocks()

        with patch.object(
            self.repository, "_link_dependencies_by_summary", return_value=0,
        ) as mock_link, patch.object(
            self.repository, "_determine_jira_status", return_value="In Progress",
        ), patch.object(
            self.repository, "_transition_issue_to_status",
        ), patch.object(
            self.repository, "_map_components", return_value=[],
        ):
            result = await self.repository.update_jira_task_from_feature(feature)

            self.assertTrue(result)
            mock_link.assert_called_once()

    async def test_update_continues_when_dependency_linking_fails(self):
        """Verify task update still succeeds if dependency linking throws."""
        feature = _make_feature(
            jira_issue_key="PM-10",
            dependencies="Non-existent Task",
            involved_people="user1",
        )
        self._setup_issue_mocks()

        with patch.object(
            self.repository, "_link_dependencies_by_summary",
            side_effect=Exception("Link error"),
        ), patch.object(
            self.repository, "_determine_jira_status", return_value="In Progress",
        ), patch.object(
            self.repository, "_transition_issue_to_status",
        ), patch.object(
            self.repository, "_map_components", return_value=[],
        ):
            result = await self.repository.update_jira_task_from_feature(feature)

            self.assertTrue(result)


class TestLinkDependenciesBySummary(unittest.TestCase):
    """Test _link_dependencies_by_summary directly."""

    def setUp(self):
        """Set up test fixtures."""
        self.repository, self.jira_repository, _ = _make_repository()

    def test_returns_zero_when_dependencies_empty(self):
        """Verify no links are created when the feature has no dependencies."""
        feature = _make_feature(dependencies=None)
        self.jira_repository.get_issue_links = MagicMock(return_value=[])

        result = self.repository._link_dependencies_by_summary("PM-1", feature, "PM")

        self.assertEqual(result, 0)

    def test_returns_zero_when_dependencies_whitespace(self):
        """Verify no links are created for whitespace-only dependencies."""
        feature = _make_feature(dependencies="   ")
        self.jira_repository.get_issue_links = MagicMock(return_value=[])

        result = self.repository._link_dependencies_by_summary("PM-1", feature, "PM")

        self.assertEqual(result, 0)

    def test_links_single_dependency(self):
        """Verify a single dependency is found and linked."""
        feature = _make_feature(dependencies="Login Page")

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-5",
        ):
            self.jira_repository.get_issue_links = MagicMock(return_value=[])

            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 1)
            self.jira_repository.link_issues.assert_called_once_with(
                dependent_issue_key="PM-1",
                dependency_issue_key="PM-5",
                link_type="Blocks",
            )

    def test_links_multiple_comma_separated_dependencies(self):
        """Verify multiple comma-separated dependencies are all linked."""
        feature = _make_feature(dependencies="Login Page, Dashboard, Settings")

        call_results = {
            "Login Page": "PM-5",
            "Dashboard": "PM-6",
            "Settings": "PM-7",
        }
        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            side_effect=lambda summary, _: call_results.get(summary.strip()),
        ):
            self.jira_repository.get_issue_links = MagicMock(return_value=[])

            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 3)
            self.assertEqual(self.jira_repository.link_issues.call_count, 3)

    def test_skips_self_dependency(self):
        """Verify the issue does not link to itself."""
        feature = _make_feature(dependencies="Self Feature")

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-1",
        ):
            self.jira_repository.get_issue_links = MagicMock(return_value=[])

            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 0)
            self.jira_repository.link_issues.assert_not_called()

    def test_removes_stale_links(self):
        """Verify stale blocking links are removed when dependencies change."""
        feature = _make_feature(dependencies="Login Page")

        existing_link = {
            "id": "link-99",
            "type": {"name": "Blocks"},
            "outwardIssue": {"key": "PM-OLD"},
        }
        self.jira_repository.get_issue_links = MagicMock(
            return_value=[existing_link],
        )

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-5",
        ):
            self.repository._link_dependencies_by_summary("PM-1", feature, "PM")

            self.jira_repository.delete_issue_link.assert_called_once_with(
                "link-99",
            )

    def test_does_not_duplicate_existing_link(self):
        """Verify already-linked dependencies are not re-created."""
        feature = _make_feature(dependencies="Login Page")

        existing_link = {
            "id": "link-10",
            "type": {"name": "Blocks"},
            "outwardIssue": {"key": "PM-5"},
        }
        self.jira_repository.get_issue_links = MagicMock(
            return_value=[existing_link],
        )

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-5",
        ):
            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 1)
            self.jira_repository.link_issues.assert_not_called()
            self.jira_repository.delete_issue_link.assert_not_called()

    def test_ignores_inward_links(self):
        """Verify inward 'Blocks' links (issues this issue blocks) are left untouched."""
        feature = _make_feature(dependencies="Login Page")

        existing_inward_link = {
            "id": "link-88",
            "type": {"name": "Blocks"},
            "inwardIssue": {"key": "PM-OLD-IN"},
        }
        self.jira_repository.get_issue_links = MagicMock(
            return_value=[existing_inward_link],
        )

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-5",
        ):
            self.repository._link_dependencies_by_summary("PM-1", feature, "PM")

            self.jira_repository.delete_issue_link.assert_not_called()
            self.jira_repository.link_issues.assert_called_once()

    def test_inward_link_does_not_prevent_outward_creation(self):
        """Verify inward links are ignored — blocker link is created independently."""
        feature = _make_feature(dependencies="Login Page")

        existing_inward_link = {
            "id": "link-77",
            "type": {"name": "Blocks"},
            "inwardIssue": {"key": "PM-5"},
        }
        self.jira_repository.get_issue_links = MagicMock(
            return_value=[existing_inward_link],
        )

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-5",
        ):
            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 1)
            self.jira_repository.link_issues.assert_called_once()
            self.jira_repository.delete_issue_link.assert_not_called()

    def test_handles_mixed_inward_and_outward_links(self):
        """Verify only stale outward (blocker) links are removed; inward links are untouched."""
        feature = _make_feature(dependencies="Login Page")

        existing_links = [
            {
                "id": "link-10",
                "type": {"name": "Blocks"},
                "inwardIssue": {"key": "PM-BLOCKED-BY-ME"},
            },
            {
                "id": "link-20",
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": "PM-STALE-BLOCKER"},
            },
        ]
        self.jira_repository.get_issue_links = MagicMock(return_value=existing_links)

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value="PM-5",
        ):
            self.repository._link_dependencies_by_summary("PM-1", feature, "PM")

            self.jira_repository.delete_issue_link.assert_called_once_with("link-20")

    def test_dependency_not_found_returns_zero(self):
        """Verify zero is returned when no matching issue is found."""
        feature = _make_feature(dependencies="Non-existent Task")

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            return_value=None,
        ):
            self.jira_repository.get_issue_links = MagicMock(return_value=[])

            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 0)
            self.jira_repository.link_issues.assert_not_called()

    def test_search_error_is_handled_gracefully(self):
        """Verify errors during dependency search do not crash the method."""
        feature = _make_feature(dependencies="Good Task, Bad Task")

        def side_effect(summary, _project):
            if "Bad" in summary:
                raise Exception("Search failed")
            return "PM-5"

        with patch.object(
            self.repository,
            "_search_issue_by_summary_in_project",
            side_effect=side_effect,
        ):
            self.jira_repository.get_issue_links = MagicMock(return_value=[])

            result = self.repository._link_dependencies_by_summary(
                "PM-1", feature, "PM",
            )

            self.assertEqual(result, 1)
            self.jira_repository.link_issues.assert_called_once()


class TestLinkIssuesDirection(unittest.TestCase):
    """Test that link_issues creates Jira links in the correct direction."""

    def test_a_blocks_link_has_correct_direction(self):
        """Verify the dependency is outward (blocks) and dependent is inward (is blocked by)."""
        jira_mock = MagicMock()
        jira_mock.server_info.return_value = {"baseUrl": "http://jira.example.com"}

        from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
            JiraServerRepository,
        )

        repo = JiraServerRepository.__new__(JiraServerRepository)
        repo.jira = jira_mock
        repo.get_issue_link_types = MagicMock(
            return_value=[{"name": "Blocks"}],
        )

        repo.link_issues(
            dependent_issue_key="TASK-1",
            dependency_issue_key="TASK-2",
            link_type="Blocks",
        )

        jira_mock.create_issue_link.assert_called_once_with(
            type="Blocks",
            inwardIssue="TASK-1",
            outwardIssue="TASK-2",
        )


if __name__ == "__main__":
    unittest.main()
