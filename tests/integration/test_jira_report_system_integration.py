"""Integration tests for Jira report system."""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.adapters.repositories.postgres.jira_report_repository import JiraReportRepository
from jira_telegram_bot.adapters.services.jira_data_service import JiraDataService
from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import APSchedulerService
from jira_telegram_bot.use_cases.generate_jira_report_use_case import GenerateJiraReportUseCase
from jira_telegram_bot.use_cases.scheduled_report_use_case import ScheduledReportUseCase
from tests.samples.jira_report_test_factory import JiraReportTestFactory


class TestJiraReportSystemIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for the complete Jira report system."""

    @classmethod
    def setUpClass(cls):
        """Set up integration test environment."""
        cls.mock_database_patches = []
        cls.mock_jira_patches = []

    def setUp(self):
        """Set up each test."""
        # The repository takes an injected DatabaseConnectionInterface now
        # and no longer builds its own engine, so the create_engine and
        # sessionmaker patches targeted names the module does not have.
        # Stubbing schema creation is what those patches were really for.
        self.schema_patch = patch.object(JiraReportRepository, '_ensure_schema_exists')
        self.schema_patch.start()

        # The repository asks its connection for a session per call, so one
        # mock connection stands in for the engine and sessionmaker that the
        # tests used to patch inside the module.
        self.mock_session = MagicMock()
        self.db_connection = MagicMock()
        self.db_connection.get_session.return_value = self.mock_session
        
        # Mock Jira repository
        self.jira_repo_patch = patch('jira_telegram_bot.adapters.services.jira_data_service.TaskManagerRepositoryInterface')
        self.mock_jira_repo = self.jira_repo_patch.start()
        # These ids are passed to getattr, which rejects a MagicMock.
        instance = self.mock_jira_repo.return_value
        instance.jira_actual_start_id = "customfield_10702"
        instance.jira_actual_end_id = "customfield_10703"
        instance.jira_target_start_id = "customfield_10109"
        instance.jira_target_end_id = "customfield_10110"
        
        # Mock scheduler
        self.scheduler_patch = patch('jira_telegram_bot.frameworks.scheduler.ap_scheduler_service.AsyncIOScheduler')
        self.mock_scheduler_class = self.scheduler_patch.start()

    def tearDown(self):
        """Clean up after each test."""
        patch.stopall()

    async def test_a_end_to_end_report_generation(self):
        """Test complete end-to-end report generation flow."""
        # Arrange
        project_key = "INTEGRATION"
        mock_issues = JiraReportTestFactory.create_multiple_issues(5)
        
        # Mock Jira data service responses
        mock_jira_repo_instance = self.mock_jira_repo.return_value
        mock_jira_repo_instance.search_issues.return_value = [
            self._create_mock_jira_issue(issue.key) for issue in mock_issues
        ]
        
        # Mock database session
        mock_session = self.mock_session
        mock_session.merge.return_value = None
        mock_session.commit.return_value = None
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        # Create services
        jira_service = JiraDataService(mock_jira_repo_instance)
        repository = JiraReportRepository(self.db_connection)
        use_case = GenerateJiraReportUseCase(jira_service, repository)
        
        # Act
        result = await use_case.generate_project_report(project_key)
        
        # Assert
        self.assertEqual(result.project_key, project_key)
        self.assertEqual(result.total_issues, 5)
        self.assertIsInstance(result.generated_at, datetime)
        mock_session.merge.assert_called()
        mock_session.commit.assert_called_once()

    async def test_a_scheduled_report_setup_and_execution(self):
        """Test scheduled report setup and execution."""
        # Arrange
        project_keys = ["TEST1", "TEST2"]
        mock_issues = JiraReportTestFactory.create_multiple_issues(3)
        
        # Mock Jira responses
        mock_jira_repo_instance = self.mock_jira_repo.return_value
        mock_jira_repo_instance.search_issues.return_value = [
            self._create_mock_jira_issue(issue.key) for issue in mock_issues
        ]
        
        # Mock database
        mock_session = self.mock_session
        mock_session.merge.return_value = None
        mock_session.commit.return_value = None
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        # Mock scheduler
        mock_scheduler_instance = self.mock_scheduler_class.return_value
        mock_scheduler_instance.add_job.return_value = None
        
        # Create services
        jira_service = JiraDataService(mock_jira_repo_instance)
        repository = JiraReportRepository(self.db_connection)
        report_use_case = GenerateJiraReportUseCase(jira_service, repository)
        scheduler_service = APSchedulerService()
        scheduled_use_case = ScheduledReportUseCase(
            report_use_case, scheduler_service, project_keys
        )
        
        # Act
        await scheduled_use_case.setup_scheduled_reports(interval_minutes=60)
        
        # Execute the scheduled job manually
        await scheduled_use_case._generate_all_reports()
        
        # Assert
        mock_scheduler_instance.add_job.assert_called_once()
        call_args = mock_scheduler_instance.add_job.call_args
        self.assertEqual(call_args.kwargs['minutes'], 60)
        self.assertEqual(call_args.kwargs['id'], 'jira_report_generation')
        
        # Verify reports were generated for both projects
        self.assertEqual(mock_session.commit.call_count, 2)

    async def test_a_concurrent_report_generation(self):
        """Test concurrent report generation for multiple projects."""
        # Arrange
        project_keys = [f"CONCURRENT{i}" for i in range(5)]
        mock_issues = JiraReportTestFactory.create_multiple_issues(2)
        
        # Mock Jira responses
        mock_jira_repo_instance = self.mock_jira_repo.return_value
        mock_jira_repo_instance.search_issues.return_value = [
            self._create_mock_jira_issue(issue.key) for issue in mock_issues
        ]
        
        # Mock database
        mock_session = self.mock_session
        mock_session.merge.return_value = None
        mock_session.commit.return_value = None
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        # Create services
        jira_service = JiraDataService(mock_jira_repo_instance)
        repository = JiraReportRepository(self.db_connection)
        use_case = GenerateJiraReportUseCase(jira_service, repository)
        
        # Act - Generate reports concurrently
        tasks = [
            asyncio.create_task(use_case.generate_project_report(project_key))
            for project_key in project_keys
        ]
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 5)
        for i, result in enumerate(results):
            self.assertEqual(result.project_key, project_keys[i])
            self.assertEqual(result.total_issues, 2)
        
        # Verify all database operations completed
        self.assertEqual(mock_session.commit.call_count, 5)

    async def test_a_error_recovery_and_resilience(self):
        """Test system resilience and error recovery."""
        # Arrange
        project_keys = ["FAIL1", "SUCCESS", "FAIL2"]
        mock_issues = JiraReportTestFactory.create_multiple_issues(1)
        
        # Mock Jira responses - simulate failures for some projects
        mock_jira_repo_instance = self.mock_jira_repo.return_value
        # One outcome per project, not per call: fetching a project makes
        # several calls (pagination, then an epic lookup per issue), so a
        # flat list was consumed by the first project alone.
        outcomes = {
            "FAIL1": Exception("Network error"),
            "SUCCESS": [self._create_mock_jira_issue("SUCCESS-1")],
            "FAIL2": Exception("Timeout error"),
        }

        def search_issues(jql, start_at=0, max_results=25, **kwargs):
            for project, outcome in outcomes.items():
                if f"project = {project}" in jql or f'project = "{project}"' in jql:
                    if isinstance(outcome, Exception):
                        raise outcome
                    return outcome if start_at == 0 else []
            return []

        mock_jira_repo_instance.search_issues.side_effect = search_issues
        
        # Mock database
        mock_session = self.mock_session
        mock_session.merge.return_value = None
        mock_session.commit.return_value = None
        
        # Create services
        jira_service = JiraDataService(mock_jira_repo_instance)
        repository = JiraReportRepository(self.db_connection)
        use_case = GenerateJiraReportUseCase(jira_service, repository)
        
        # Act & Assert - Test individual project failures
        with self.assertRaises(RuntimeError):
            await use_case.generate_project_report("FAIL1")
        
        # Successful project should work
        result = await use_case.generate_project_report("SUCCESS")
        self.assertEqual(result.project_key, "SUCCESS")
        
        with self.assertRaises(RuntimeError):
            await use_case.generate_project_report("FAIL2")

    async def test_a_large_dataset_performance(self):
        """Test system performance with large datasets."""
        # Arrange
        project_key = "LARGE_PROJECT"
        mock_large_issues = JiraReportTestFactory.create_multiple_issues(1000)
        
        # Mock Jira responses - simulate pagination
        mock_jira_repo_instance = self.mock_jira_repo.return_value
        
        # Create batches for pagination simulation
        # Pagination pulls 25 at a time and then makes one epic lookup per
        # issue, so a fixed list of batches runs out and the mock raises
        # StopIteration. Serving pages on demand tracks whatever the
        # repository actually asks for.
        issues = [
            self._create_mock_jira_issue(issue.key)
            for issue in mock_large_issues
        ]

        def search_issues(jql, start_at=0, max_results=25, **kwargs):
            if "project = " in jql and "key" not in jql:
                return issues[start_at:start_at + max_results]
            return []

        mock_jira_repo_instance.search_issues.side_effect = search_issues
        
        # Mock database
        mock_session = self.mock_session
        mock_session.merge.return_value = None
        mock_session.commit.return_value = None
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        # Create services
        jira_service = JiraDataService(mock_jira_repo_instance)
        repository = JiraReportRepository(self.db_connection)
        use_case = GenerateJiraReportUseCase(jira_service, repository)
        
        # Act
        start_time = asyncio.get_event_loop().time()
        result = await use_case.generate_project_report(project_key)
        end_time = asyncio.get_event_loop().time()
        
        # Assert
        self.assertEqual(result.total_issues, 1000)
        execution_time = end_time - start_time
        self.assertLess(execution_time, 30.0)  # Should complete within 30 seconds
        
        # Verify all issues were processed
        self.assertEqual(mock_session.merge.call_count, 1000)

    def _create_mock_jira_issue(self, key: str):
        """Create a mock Jira issue for testing."""
        from tests.unit_tests.adapters.services.test_jira_data_service import MockJiraIssue
        issue = MockJiraIssue(key)
        issue.fields.issuetype.name = "Story"  # Ensure it's not an Epic
        return issue


if __name__ == "__main__":
    unittest.main()
