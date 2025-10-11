"""Unit tests for Jira report generation use case."""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.use_cases.generate_jira_report_use_case import GenerateJiraReportUseCase


class TestGenerateJiraReportUseCase(unittest.TestCase):
    """Test cases for GenerateJiraReportUseCase."""

    def setUp(self) -> None:
        """Set up test dependencies."""
        self.mock_jira_service = AsyncMock()
        self.mock_repository = AsyncMock()
        self.use_case = GenerateJiraReportUseCase(
            jira_service=self.mock_jira_service,
            report_repository=self.mock_repository,
        )

    async def test_generate_project_report_success(self) -> None:
        """Test successful project report generation."""
        # Arrange
        project_key = "TEST"
        mock_issues = [
            JiraIssueDetail(
                key="TEST-1",
                summary="Test issue",
                task_type="Story",
                reporter="Test User",
                status="Open",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.return_value = None

        # Act
        result = await self.use_case.generate_project_report(project_key)

        # Assert
        self.assertIsInstance(result, ProjectReport)
        self.assertEqual(result.project_key, project_key)
        self.assertEqual(result.total_issues, 1)
        self.assertEqual(len(result.issues), 1)
        
        self.mock_jira_service.fetch_project_issues.assert_called_once_with(project_key)
        self.mock_repository.store_issues.assert_called_once_with(mock_issues)

    async def test_generate_project_report_empty_key(self) -> None:
        """Test project report generation with empty key."""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            await self.use_case.generate_project_report("")
        
        self.assertIn("Project key cannot be empty", str(context.exception))

    async def test_generate_multi_project_report_success(self) -> None:
        """Test successful multi-project report generation."""
        # Arrange
        project_keys = ["TEST1", "TEST2"]
        mock_issues = [
            JiraIssueDetail(
                key="TEST-1",
                summary="Test issue",
                task_type="Story",
                reporter="Test User",
                status="Open",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]
        
        self.mock_jira_service.fetch_project_issues.return_value = mock_issues
        self.mock_repository.store_issues.return_value = None

        # Act
        results = await self.use_case.generate_multi_project_report(project_keys)

        # Assert
        self.assertEqual(len(results), 2)
        for i, result in enumerate(results):
            self.assertIsInstance(result, ProjectReport)
            self.assertEqual(result.project_key, project_keys[i])
            self.assertEqual(result.total_issues, 1)

    async def test_generate_multi_project_report_empty_list(self) -> None:
        """Test multi-project report generation with empty list."""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            await self.use_case.generate_multi_project_report([])
        
        self.assertIn("Project keys list cannot be empty", str(context.exception))


if __name__ == "__main__":
    import asyncio
    
    def run_async_test(test_func):
        """Helper to run async test methods."""
        def wrapper(self):
            asyncio.run(test_func(self))
        return wrapper

    # Convert async test methods to run with asyncio
    TestGenerateJiraReportUseCase.test_generate_project_report_success = run_async_test(
        TestGenerateJiraReportUseCase.test_generate_project_report_success
    )
    TestGenerateJiraReportUseCase.test_generate_project_report_empty_key = run_async_test(
        TestGenerateJiraReportUseCase.test_generate_project_report_empty_key
    )
    TestGenerateJiraReportUseCase.test_generate_multi_project_report_success = run_async_test(
        TestGenerateJiraReportUseCase.test_generate_multi_project_report_success
    )
    TestGenerateJiraReportUseCase.test_generate_multi_project_report_empty_list = run_async_test(
        TestGenerateJiraReportUseCase.test_generate_multi_project_report_empty_list
    )
    
    unittest.main()
