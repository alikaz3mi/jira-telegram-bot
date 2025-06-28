"""Unit tests for GenerateJiraReportUseCase."""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.use_cases.generate_jira_report_use_case import GenerateJiraReportUseCase
from tests.samples.jira_report_test_factory import JiraReportTestFactory


class TestGenerateJiraReportUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for GenerateJiraReportUseCase."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_jira_service = AsyncMock()
        self.mock_repository = AsyncMock()
        self.use_case = GenerateJiraReportUseCase(
            jira_service=self.mock_jira_service,
            report_repository=self.mock_repository,
        )

    async def test_a_generate_project_report_success(self):
        """Test successful project report generation."""
        project_key = "TEST"
        mock_issues = JiraReportTestFactory.create_multiple_issues(3)
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.return_value = None

        result = await self.use_case.generate_project_report(project_key)

        self.assertIsInstance(result, ProjectReport)
        self.assertEqual(result.project_key, project_key)
        self.assertEqual(result.total_issues, 3)
        self.assertEqual(len(result.issues), 3)
        
        self.mock_jira_service.fetch_project_issues.assert_called_once_with(project_key)
        self.mock_repository.store_issues.assert_called_once_with(mock_issues)

    async def test_a_generate_project_report_empty_key(self):
        """Test project report generation with empty key."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.generate_project_report("")
        
        self.assertIn("Project key cannot be empty", str(context.exception))
        self.mock_jira_service.fetch_project_issues.assert_not_called()
        self.mock_repository.store_issues.assert_not_called()

    async def test_a_generate_project_report_whitespace_key(self):
        """Test project report generation with whitespace-only key."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.generate_project_report("   ")
        
        self.assertIn("Project key cannot be empty", str(context.exception))

    async def test_a_generate_project_report_none_key(self):
        """Test project report generation with None key."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.generate_project_report(None)
        
        self.assertIn("Project key cannot be empty", str(context.exception))

    async def test_a_generate_project_report_no_issues(self):
        """Test project report generation with no issues."""
        project_key = "EMPTY"
        
        self.mock_jira_service.fetch_project_issues.return_value = []
        self.mock_repository.store_issues.return_value = None

        result = await self.use_case.generate_project_report(project_key)

        self.assertEqual(result.total_issues, 0)
        self.assertEqual(len(result.issues), 0)
        self.mock_repository.store_issues.assert_called_once_with([])

    async def test_a_generate_project_report_service_failure(self):
        """Test project report generation when service fails."""
        project_key = "TEST"
        
        self.mock_jira_service.fetch_project_issues.side_effect = Exception("Service error")

        with self.assertRaises(RuntimeError) as context:
            await self.use_case.generate_project_report(project_key)
        
        self.assertIn("Report generation failed", str(context.exception))
        self.assertIn("Service error", str(context.exception))
        self.mock_repository.store_issues.assert_not_called()

    async def test_a_generate_project_report_repository_failure(self):
        """Test project report generation when repository fails."""
        project_key = "TEST"
        mock_issues = JiraReportTestFactory.create_multiple_issues(2)
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.side_effect = Exception("Database error")

        with self.assertRaises(RuntimeError) as context:
            await self.use_case.generate_project_report(project_key)
        
        self.assertIn("Report generation failed", str(context.exception))
        self.assertIn("Database error", str(context.exception))

    async def test_a_generate_multi_project_report_success(self):
        """Test successful multi-project report generation."""
        project_keys = ["TEST1", "TEST2", "TEST3"]
        mock_issues = JiraReportTestFactory.create_multiple_issues(2)
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.return_value = None

        results = await self.use_case.generate_multi_project_report(project_keys)

        self.assertEqual(len(results), 3)
        for i, result in enumerate(results):
            self.assertIsInstance(result, ProjectReport)
            self.assertEqual(result.project_key, project_keys[i])
            self.assertEqual(result.total_issues, 2)

        self.assertEqual(self.mock_jira_service.fetch_project_issues.call_count, 3)
        self.assertEqual(self.mock_repository.store_issues.call_count, 3)

    async def test_a_generate_multi_project_report_empty_list(self):
        """Test multi-project report generation with empty list."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.generate_multi_project_report([])
        
        self.assertIn("Project keys list cannot be empty", str(context.exception))
        self.mock_jira_service.fetch_project_issues.assert_not_called()

    async def test_a_generate_multi_project_report_partial_failure(self):
        """Test multi-project report generation with one project failing."""
        project_keys = ["TEST1", "TEST2"]
        mock_issues = JiraReportTestFactory.create_multiple_issues(1)
        
        self.mock_jira_service.fetch_project_issues.side_effect = [
            mock_issues,  # First project succeeds
            Exception("Service error"),  # Second project fails
        ]
        self.mock_repository.store_issues.return_value = None

        with self.assertRaises(RuntimeError) as context:
            await self.use_case.generate_multi_project_report(project_keys)
        
        self.assertIn("Multi-project report generation failed at TEST2", str(context.exception))
        self.assertEqual(self.mock_jira_service.fetch_project_issues.call_count, 2)
        self.assertEqual(self.mock_repository.store_issues.call_count, 1)

    async def test_a_generate_project_report_validates_result(self):
        """Test that generated report has correct timestamp."""
        project_key = "TEST"
        mock_issues = JiraReportTestFactory.create_multiple_issues(1)
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.return_value = None

        before_time = datetime.now()
        result = await self.use_case.generate_project_report(project_key)
        after_time = datetime.now()

        self.assertGreaterEqual(result.generated_at, before_time)
        self.assertLessEqual(result.generated_at, after_time)

    async def test_a_generate_project_report_large_dataset(self):
        """Test project report generation with large dataset."""
        project_key = "LARGE"
        mock_issues = JiraReportTestFactory.create_multiple_issues(1000)
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.return_value = None

        result = await self.use_case.generate_project_report(project_key)

        self.assertEqual(result.total_issues, 1000)
        self.assertEqual(len(result.issues), 1000)


if __name__ == "__main__":
    unittest.main()
