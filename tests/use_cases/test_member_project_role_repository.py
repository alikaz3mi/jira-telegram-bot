"""Unit tests for MemberProjectRoleRepository."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from jira_telegram_bot.adapters.repositories.postgres.member_project_role_repository import (
    MemberProjectRoleRepository,
)
from jira_telegram_bot.entities.member_project_role import (
    MemberProjectRole,
    MemberRoleSummary,
)


class TestMemberProjectRoleRepository(unittest.TestCase):
    """Test MemberProjectRoleRepository."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.repo = MemberProjectRoleRepository(session=self.mock_session)
        self.test_member_id = "account_123"
        self.test_project_key = "PROJ"
        self.test_role = "Developer"
        self.test_rank = "Senior"

    def test_set_overall_role_creates_new(self):
        """Test setting overall role creates new record when none exists."""
        # Arrange
        self.mock_session.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=None)),  # existing check
            MagicMock(
                fetchone=MagicMock(
                    return_value=(
                        1,
                        self.test_member_id,
                        None,
                        self.test_role,
                        self.test_rank,
                        True,
                        datetime(2024, 1, 1),
                        datetime(2024, 1, 1),
                    )
                )
            ),  # insert
        ]

        # Act
        result = self.repo.set_overall_role(
            self.test_member_id, self.test_role, self.test_rank
        )

        # Assert
        self.assertEqual(result.member_id, self.test_member_id)
        self.assertEqual(result.role, self.test_role)
        self.assertEqual(result.rank, self.test_rank)
        self.assertTrue(result.is_overall)
        self.assertIsNone(result.project_key)
        self.mock_session.commit.assert_called()

    def test_set_overall_role_updates_existing(self):
        """Test setting overall role updates existing record."""
        # Arrange
        existing_role = MemberProjectRole(
            id=1,
            member_id=self.test_member_id,
            project_key=None,
            role="Junior Developer",
            rank="Junior",
            is_overall=True,
        )

        self.mock_session.execute.side_effect = [
            MagicMock(
                fetchone=MagicMock(
                    return_value=(
                        existing_role.id,
                        existing_role.member_id,
                        existing_role.project_key,
                        existing_role.role,
                        existing_role.rank,
                        existing_role.is_overall,
                        datetime(2024, 1, 1),
                        datetime(2024, 1, 1),
                    )
                )
            ),  # existing check
            MagicMock(
                fetchone=MagicMock(
                    return_value=(
                        1,
                        self.test_member_id,
                        None,
                        self.test_role,
                        self.test_rank,
                        True,
                        datetime(2024, 1, 1),
                        datetime(2024, 1, 2),
                    )
                )
            ),  # update
        ]

        # Act
        result = self.repo.set_overall_role(
            self.test_member_id, self.test_role, self.test_rank
        )

        # Assert
        self.assertEqual(result.role, self.test_role)
        self.assertEqual(result.rank, self.test_rank)
        self.mock_session.commit.assert_called()

    def test_set_project_role_creates_new(self):
        """Test setting project role creates new record."""
        # Arrange
        self.mock_session.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=None)),  # existing check
            MagicMock(
                fetchone=MagicMock(
                    return_value=(
                        1,
                        self.test_member_id,
                        self.test_project_key,
                        self.test_role,
                        self.test_rank,
                        False,
                        datetime(2024, 1, 1),
                        datetime(2024, 1, 1),
                    )
                )
            ),  # insert
        ]

        # Act
        result = self.repo.set_project_role(
            self.test_member_id, self.test_project_key, self.test_role, self.test_rank
        )

        # Assert
        self.assertEqual(result.member_id, self.test_member_id)
        self.assertEqual(result.project_key, self.test_project_key)
        self.assertEqual(result.role, self.test_role)
        self.assertEqual(result.rank, self.test_rank)
        self.assertFalse(result.is_overall)

    def test_get_member_role_summary(self):
        """Test getting complete role summary for a member."""
        # Arrange
        mock_rows = [
            (
                1,
                self.test_member_id,
                None,
                "Developer",
                "Senior",
                True,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
            (
                2,
                self.test_member_id,
                "PROJ1",
                "Lead Developer",
                "Senior",
                False,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
            (
                3,
                self.test_member_id,
                "PROJ2",
                "Developer",
                "Mid",
                False,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
        ]

        self.mock_session.execute.return_value = mock_rows

        # Act
        result = self.repo.get_member_role_summary(self.test_member_id)

        # Assert
        self.assertIsInstance(result, MemberRoleSummary)
        self.assertEqual(result.member_id, self.test_member_id)
        self.assertIsNotNone(result.overall_role)
        self.assertEqual(result.overall_role.role, "Developer")
        self.assertEqual(len(result.project_roles), 2)
        self.assertEqual(result.project_roles[0].project_key, "PROJ1")
        self.assertEqual(result.project_roles[1].project_key, "PROJ2")

    def test_get_project_role(self):
        """Test getting member's role for specific project."""
        # Arrange
        mock_row = (
            1,
            self.test_member_id,
            self.test_project_key,
            self.test_role,
            self.test_rank,
            False,
            datetime(2024, 1, 1),
            datetime(2024, 1, 1),
        )

        self.mock_session.execute.return_value.fetchone.return_value = mock_row

        # Act
        result = self.repo.get_project_role(self.test_member_id, self.test_project_key)

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.project_key, self.test_project_key)
        self.assertEqual(result.role, self.test_role)

    def test_get_overall_role(self):
        """Test getting member's overall role."""
        # Arrange
        mock_row = (
            1,
            self.test_member_id,
            None,
            self.test_role,
            self.test_rank,
            True,
            datetime(2024, 1, 1),
            datetime(2024, 1, 1),
        )

        self.mock_session.execute.return_value.fetchone.return_value = mock_row

        # Act
        result = self.repo.get_overall_role(self.test_member_id)

        # Assert
        self.assertIsNotNone(result)
        self.assertTrue(result.is_overall)
        self.assertEqual(result.role, self.test_role)

    def test_delete_project_role(self):
        """Test deleting project role."""
        # Arrange
        self.mock_session.execute.return_value.rowcount = 1

        # Act
        result = self.repo.delete_project_role(
            self.test_member_id, self.test_project_key
        )

        # Assert
        self.assertTrue(result)
        self.mock_session.commit.assert_called()

    def test_delete_project_role_not_found(self):
        """Test deleting non-existent project role returns False."""
        # Arrange
        self.mock_session.execute.return_value.rowcount = 0

        # Act
        result = self.repo.delete_project_role(
            self.test_member_id, self.test_project_key
        )

        # Assert
        self.assertFalse(result)

    def test_delete_all_roles(self):
        """Test deleting all roles for a member."""
        # Arrange
        self.mock_session.execute.return_value.rowcount = 3

        # Act
        result = self.repo.delete_all_roles(self.test_member_id)

        # Assert
        self.assertEqual(result, 3)
        self.mock_session.commit.assert_called()

    def test_get_members_by_project(self):
        """Test getting all members in a project."""
        # Arrange
        mock_rows = [
            (
                1,
                "account_1",
                self.test_project_key,
                "Developer",
                "Senior",
                False,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
            (
                2,
                "account_2",
                self.test_project_key,
                "QA",
                "Mid",
                False,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
        ]

        self.mock_session.execute.return_value = mock_rows

        # Act
        result = self.repo.get_members_by_project(self.test_project_key)

        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].member_id, "account_1")
        self.assertEqual(result[1].member_id, "account_2")

    def test_get_members_by_role(self):
        """Test getting all members with specific role."""
        # Arrange
        mock_rows = [
            (
                1,
                "account_1",
                "PROJ1",
                "Developer",
                "Senior",
                False,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
            (
                2,
                "account_2",
                "PROJ2",
                "Developer",
                "Junior",
                False,
                datetime(2024, 1, 1),
                datetime(2024, 1, 1),
            ),
        ]

        self.mock_session.execute.return_value = mock_rows

        # Act
        result = self.repo.get_members_by_role("Developer")

        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].role, "Developer")
        self.assertEqual(result[1].role, "Developer")


class TestMemberProjectRoleEntity(unittest.TestCase):
    """Test MemberProjectRole entity methods."""

    def test_is_project_specific(self):
        """Test is_project_specific method."""
        # Project-specific role
        role1 = MemberProjectRole(
            member_id="account_1",
            project_key="PROJ",
            role="Developer",
            is_overall=False,
        )
        self.assertTrue(role1.is_project_specific())

        # Overall role
        role2 = MemberProjectRole(
            member_id="account_1",
            project_key=None,
            role="Developer",
            is_overall=True,
        )
        self.assertFalse(role2.is_project_specific())

    def test_display_name(self):
        """Test display name generation."""
        # With rank and project
        role1 = MemberProjectRole(
            member_id="account_1",
            project_key="PROJ",
            role="Developer",
            rank="Senior",
        )
        self.assertEqual(role1.display_name(), "Senior Developer in PROJ")

        # Without rank, overall
        role2 = MemberProjectRole(
            member_id="account_1",
            project_key=None,
            role="Developer",
            is_overall=True,
        )
        self.assertEqual(role2.display_name(), "Developer (Overall)")


class TestMemberRoleSummary(unittest.TestCase):
    """Test MemberRoleSummary entity methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.overall_role = MemberProjectRole(
            member_id="account_1",
            project_key=None,
            role="Developer",
            rank="Senior",
            is_overall=True,
        )

        self.project_role1 = MemberProjectRole(
            member_id="account_1",
            project_key="PROJ1",
            role="Lead Developer",
            rank="Senior",
        )

        self.project_role2 = MemberProjectRole(
            member_id="account_1",
            project_key="PROJ2",
            role="Developer",
            rank="Mid",
        )

        self.summary = MemberRoleSummary(
            member_id="account_1",
            overall_role=self.overall_role,
            project_roles=[self.project_role1, self.project_role2],
        )

    def test_has_overall_role(self):
        """Test has_overall_role method."""
        self.assertTrue(self.summary.has_overall_role())

        summary_no_overall = MemberRoleSummary(member_id="account_1", project_roles=[])
        self.assertFalse(summary_no_overall.has_overall_role())

    def test_get_role_for_project(self):
        """Test get_role_for_project method."""
        role = self.summary.get_role_for_project("PROJ1")
        self.assertIsNotNone(role)
        self.assertEqual(role.project_key, "PROJ1")

        role_not_found = self.summary.get_role_for_project("PROJ3")
        self.assertIsNone(role_not_found)

    def test_get_effective_role_with_project_specific(self):
        """Test get_effective_role returns project-specific role when available."""
        role = self.summary.get_effective_role("PROJ1")
        self.assertIsNotNone(role)
        self.assertEqual(role.project_key, "PROJ1")
        self.assertEqual(role.role, "Lead Developer")

    def test_get_effective_role_falls_back_to_overall(self):
        """Test get_effective_role falls back to overall role."""
        role = self.summary.get_effective_role("PROJ3")
        self.assertIsNotNone(role)
        self.assertEqual(role.role, "Developer")
        self.assertTrue(role.is_overall)

    def test_get_effective_role_no_project_key(self):
        """Test get_effective_role with no project key returns overall."""
        role = self.summary.get_effective_role()
        self.assertIsNotNone(role)
        self.assertTrue(role.is_overall)


if __name__ == "__main__":
    unittest.main()
