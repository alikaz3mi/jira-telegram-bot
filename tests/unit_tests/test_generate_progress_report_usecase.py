import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from jira_telegram_bot.entities.jira.issue import JiraIssue
from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport
from jira_telegram_bot.use_cases.ai_agents.generate_progress_report_usecase import GenerateProgressReportUseCase


class TestGenerateProgressReportUseCase(unittest.TestCase):
    """Test cases for GenerateProgressReportUseCase."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_prompt_catalog = MagicMock()
        self.mock_ai_service = AsyncMock()
        self.mock_repository = AsyncMock()
        self.use_case = GenerateProgressReportUseCase(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
            repository=self.mock_repository
        )

    async def test_execute_with_valid_input(self):
        """Test successful execution with valid input."""
        # Arrange
        assignee = "john_doe"
        sprint_label = "Sprint 1"
        selected_issue_keys = ["PROJ-123", "PROJ-456"]
        available_tasks = [
            JiraIssue(key="PROJ-123", summary="Task 1", assignee="john_doe"),
            JiraIssue(key="PROJ-456", summary="Task 2", assignee="john_doe"),
        ]
        raw_transcript = "I worked on authentication and fixed a bug"
        
        # Mock AI service response (via _process_with_ai)
        ai_response = {
            "reports": [
                {
                    "issue_key": "PROJ-123",
                    "progress": "Implemented authentication",
                    "blockers": "None",
                    "time_spent": "2h"
                },
                {
                    "issue_key": "PROJ-456", 
                    "progress": "Fixed critical bug",
                    "blockers": "None",
                    "time_spent": "1h"
                }
            ]
        }
        
        # Mock the _process_with_ai method
        self.use_case._process_with_ai = AsyncMock(return_value=ai_response)
        
        # Mock repository response
        stored_reports = [
            ProgressReport(
                issue_key="PROJ-123",
                progress="Implemented authentication",
                blockers="None",
                time_spent="2h",
                assignee="john_doe",
                reported_at=datetime.utcnow(),
                report_id="uuid-123"
            ),
            ProgressReport(
                issue_key="PROJ-456",
                progress="Fixed critical bug",
                blockers="None",
                time_spent="1h",
                assignee="john_doe",
                reported_at=datetime.utcnow(),
                report_id="uuid-456"
            )
        ]
        
        self.mock_repository.save_reports.return_value = stored_reports
        
        # Act
        result = await self.use_case.execute(
            assignee=assignee,
            sprint_label=sprint_label,
            selected_issue_keys=selected_issue_keys,
            available_tasks=available_tasks,
            raw_transcript=raw_transcript
        )
        
        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].issue_key, "PROJ-123")
        self.assertEqual(result[1].issue_key, "PROJ-456")
        self.assertIsNotNone(result[0].assignee)
        self.assertIsNotNone(result[0].reported_at)
        self.assertIsNotNone(result[0].report_id)
        
        # Verify _process_with_ai was called correctly
        self.use_case._process_with_ai.assert_called_once()
        
        # Verify repository was called
        self.mock_repository.save_reports.assert_called_once()

    async def test_execute_with_empty_assignee_raises_error(self):
        """Test that empty assignee raises ValueError."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(
                assignee="",
                sprint_label="Sprint 1",
                selected_issue_keys=[],
                available_tasks=[],
                raw_transcript="Some progress"
            )
        
        self.assertIn("Assignee cannot be empty", str(context.exception))

    async def test_execute_with_empty_sprint_label_raises_error(self):
        """Test that empty sprint label raises ValueError."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(
                assignee="john_doe",
                sprint_label="",
                selected_issue_keys=[],
                available_tasks=[],
                raw_transcript="Some progress"
            )
        
        self.assertIn("Sprint label cannot be empty", str(context.exception))

    async def test_execute_with_empty_transcript_raises_error(self):
        """Test that empty transcript raises ValueError."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(
                assignee="john_doe",
                sprint_label="Sprint 1",
                selected_issue_keys=[],
                available_tasks=[],
                raw_transcript=""
            )
        
        self.assertIn("Raw transcript cannot be empty", str(context.exception))

    async def test_execute_with_whitespace_only_input_raises_error(self):
        """Test that whitespace-only input raises ValueError."""
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(
                assignee="   ",
                sprint_label="Sprint 1",
                selected_issue_keys=[],
                available_tasks=[],
                raw_transcript="Some progress"
            )
        
        self.assertIn("Assignee cannot be empty", str(context.exception))

    async def test_get_reports_by_assignee_and_sprint(self):
        """Test retrieving reports by assignee and sprint."""
        # Arrange
        assignee = "jane_doe"
        sprint_label = "Sprint 2"
        limit = 10
        
        expected_reports = [
            ProgressReport(
                issue_key="PROJ-789",
                progress="Feature completed",
                blockers="None",
                time_spent="3h",
                assignee=assignee,
                reported_at=datetime.utcnow(),
                report_id="uuid-789"
            )
        ]
        
        self.mock_repository.get_reports_by_assignee_and_sprint.return_value = expected_reports
        
        # Act
        result = await self.use_case.get_reports_by_assignee_and_sprint(
            assignee=assignee,
            sprint_label=sprint_label,
            limit=limit
        )
        
        # Assert
        self.assertEqual(result, expected_reports)
        self.mock_repository.get_reports_by_assignee_and_sprint.assert_called_once_with(
            assignee=assignee,
            sprint_label=sprint_label,
            limit=limit
        )


if __name__ == '__main__':
    import asyncio
    
    # Helper to run async tests
    def async_test(func):
        def wrapper(*args, **kwargs):
            return asyncio.run(func(*args, **kwargs))
        return wrapper
    
    # Apply async_test decorator to async test methods
    for name in dir(TestGenerateProgressReportUseCase):
        if name.startswith('test_') and 'async' in name:
            method = getattr(TestGenerateProgressReportUseCase, name)
            if callable(method):
                setattr(TestGenerateProgressReportUseCase, name, async_test(method))
    
    unittest.main()
