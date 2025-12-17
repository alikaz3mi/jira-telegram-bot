"""Unit tests for ManageMemberRolesUseCase."""

import unittest
from unittest.mock import MagicMock
from datetime import datetime

# Avoid circular imports by importing only what we need
import sys
sys.path.insert(0, "/home/alikazemi/project/jira-telegram-bot")

from jira_telegram_bot.entities.member_project_role import (
    MemberProjectRole,
    MemberRoleSummary,
)

# Import repository and use case classes directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "manage_member_roles",
    "/home/alikazemi/project/jira-telegram-bot/jira_telegram_bot/use_cases/team_evaluation/manage_member_roles.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ManageMemberRolesUseCase = module.ManageMemberRolesUseCase


class TestManageMemberRolesUseCase(unittest.TestCase):
    """Test ManageMemberRolesUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_repo = MagicMock()
        self.use_case = ManageMemberRolesUseCase(member_role_repo=self.mock_repo)
        self.test_member_id = "account_123"
        self.test_project_key = "PROJ"
        self.test_role = "Developer"
        self.test_rank = "Senior"

    def test_set_overall_role(self):
        """Test setting overall role."""
        # Arrange
        expected_role = MemberProjectRole(
            id=1,
            member_id=self.test_member_id,
            project_key=None,
            role=self.test_role,
            rank=self.test_rank,
            is_overall=True,
        )
        self.mock_repo.set_overall_role.return_value = expected_role

        # Act
        result = self.use_case.set_overall_role(
            self.test_member_id, self.test_role, self.test_rank
        )

        # Assert
        self.assertEqual(result, expected_role)
        self.mock_repo.set_overall_role.assert_called_once_with(
            member_id=self.test_member_id, role=self.test_role, rank=self.test_rank
        )

    def test_set_project_role(self):
        """Test setting project role."""
        # Arrange
        expected_role = MemberProjectRole(
            id=1,
            member_id=self.test_member_id,
            project_key=self.test_project_key,
            role=self.test_role,
            rank=self.test_rank,
            is_overall=False,
        )
        self.mock_repo.set_project_role.return_value = expected_role

        # Act
        result = self.use_case.set_project_role(
            self.test_member_id, self.test_project_key, self.test_role, self.test_rank
        )

        # Assert
        self.assertEqual(result, expected_role)
        self.mock_repo.set_project_role.assert_called_once_with(
            member_id=self.test_member_id,
            project_key=self.test_project_key,
            role=self.test_role,
            rank=self.test_rank,
        )

    def test_get_member_roles(self):
        """Test getting member role summary."""
        # Arrange
        overall_role = MemberProjectRole(
            member_id=self.test_member_id,
            role="Developer",
            rank="Senior",
            is_overall=True,
        )
        project_role = MemberProjectRole(
            member_id=self.test_member_id,
            project_key="PROJ1",
            role="Lead Developer",
            rank="Senior",
        )
        expected_summary = MemberRoleSummary(
            member_id=self.test_member_id,
            overall_role=overall_role,
            project_roles=[project_role],
        )
        self.mock_repo.get_member_role_summary.return_value = expected_summary

        # Act
        result = self.use_case.get_member_roles(self.test_member_id)

        # Assert
        self.assertEqual(result, expected_summary)
        self.mock_repo.get_member_role_summary.assert_called_once_with(
            self.test_member_id
        )

    def test_get_effective_role_with_project(self):
        """Test getting effective role with project context."""
        # Arrange
        overall_role = MemberProjectRole(
            member_id=self.test_member_id,
            role="Developer",
            is_overall=True,
        )
        project_role = MemberProjectRole(
            member_id=self.test_member_id,
            project_key=self.test_project_key,
            role="Lead Developer",
        )
        summary = MemberRoleSummary(
            member_id=self.test_member_id,
            overall_role=overall_role,
            project_roles=[project_role],
        )
        self.mock_repo.get_member_role_summary.return_value = summary

        # Act
        result = self.use_case.get_effective_role(
            self.test_member_id, self.test_project_key
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.project_key, self.test_project_key)
        self.assertEqual(result.role, "Lead Developer")

    def test_get_effective_role_fallback_to_overall(self):
        """Test effective role falls back to overall when no project role."""
        # Arrange
        overall_role = MemberProjectRole(
            member_id=self.test_member_id,
            role="Developer",
            is_overall=True,
        )
        summary = MemberRoleSummary(
            member_id=self.test_member_id,
            overall_role=overall_role,
            project_roles=[],
        )
        self.mock_repo.get_member_role_summary.return_value = summary

        # Act
        result = self.use_case.get_effective_role(self.test_member_id, "NONEXISTENT")

        # Assert
        self.assertIsNotNone(result)
        self.assertTrue(result.is_overall)
        self.assertEqual(result.role, "Developer")

    def test_delete_project_role(self):
        """Test deleting project role."""
        # Arrange
        self.mock_repo.delete_project_role.return_value = True

        # Act
        result = self.use_case.delete_project_role(
            self.test_member_id, self.test_project_key
        )

        # Assert
        self.assertTrue(result)
        self.mock_repo.delete_project_role.assert_called_once_with(
            self.test_member_id, self.test_project_key
        )

    def test_delete_all_roles(self):
        """Test deleting all roles."""
        # Arrange
        self.mock_repo.delete_all_roles.return_value = 3

        # Act
        result = self.use_case.delete_all_roles(self.test_member_id)

        # Assert
        self.assertEqual(result, 3)
        self.mock_repo.delete_all_roles.assert_called_once_with(self.test_member_id)

    def test_get_project_members(self):
        """Test getting all project members."""
        # Arrange
        roles = [
            MemberProjectRole(
                member_id="account_1",
                project_key=self.test_project_key,
                role="Developer",
            ),
            MemberProjectRole(
                member_id="account_2",
                project_key=self.test_project_key,
                role="QA",
            ),
        ]
        self.mock_repo.get_members_by_project.return_value = roles

        # Act
        result = self.use_case.get_project_members(self.test_project_key)

        # Assert
        self.assertEqual(len(result), 2)
        self.mock_repo.get_members_by_project.assert_called_once_with(
            self.test_project_key
        )

    def test_get_members_by_role(self):
        """Test getting members by role."""
        # Arrange
        roles = [
            MemberProjectRole(
                member_id="account_1",
                project_key="PROJ1",
                role="Developer",
            ),
            MemberProjectRole(
                member_id="account_2",
                project_key="PROJ2",
                role="Developer",
            ),
        ]
        self.mock_repo.get_members_by_role.return_value = roles

        # Act
        result = self.use_case.get_members_by_role("Developer")

        # Assert
        self.assertEqual(len(result), 2)
        self.mock_repo.get_members_by_role.assert_called_once_with("Developer")


if __name__ == "__main__":
    unittest.main()
