"""Unit tests for JiraReportRepository."""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.adapters.repositories.jira_report_repository import JiraReportRepository
from jira_telegram_bot.adapters.repositories.jira_report_repository import JiraTaskModel
from jira_telegram_bot.entities.jira_report import ProjectReport
from tests.samples.jira_report_test_factory import JiraReportTestFactory


class TestJiraReportRepository(unittest.IsolatedAsyncioTestCase):
    """Test cases for JiraReportRepository."""

    def setUp(self):
        """Set up test dependencies."""
        with patch('jira_telegram_bot.adapters.repositories.jira_report_repository.create_engine'), \
             patch('jira_telegram_bot.adapters.repositories.jira_report_repository.sessionmaker'), \
             patch.object(JiraReportRepository, '_ensure_schema_exists'):
            self.repository = JiraReportRepository()
            self.mock_session = MagicMock()
            self.repository._session_maker.return_value = self.mock_session

    async def test_a_store_issues_success(self):
        """Test successful issue storage."""
        issues = JiraReportTestFactory.create_multiple_issues(3)
        
        self.mock_session.merge.return_value = None
        self.mock_session.commit.return_value = None

        await self.repository.store_issues(issues)

        self.assertEqual(self.mock_session.merge.call_count, 3)
        self.mock_session.commit.assert_called_once()
        self.mock_session.rollback.assert_not_called()
        self.mock_session.close.assert_called_once()

    async def test_a_store_issues_empty_list(self):
        """Test storing empty issues list."""
        await self.repository.store_issues([])

        self.mock_session.merge.assert_not_called()
        self.mock_session.commit.assert_not_called()
        self.mock_session.close.assert_not_called()

    async def test_a_store_issues_database_error(self):
        """Test issue storage with database error."""
        issues = JiraReportTestFactory.create_multiple_issues(2)
        
        self.mock_session.merge.side_effect = Exception("Database error")

        with self.assertRaises(Exception):
            await self.repository.store_issues(issues)

        self.mock_session.rollback.assert_called_once()
        self.mock_session.close.assert_called_once()

    async def test_a_get_project_report_success(self):
        """Test successful project report retrieval."""
        project_key = "TEST"
        mock_tasks = [self._create_mock_task_model("TEST-1"), self._create_mock_task_model("TEST-2")]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = mock_tasks

        result = await self.repository.get_project_report(project_key)

        self.assertIsInstance(result, ProjectReport)
        self.assertEqual(result.project_key, project_key)
        self.assertEqual(result.total_issues, 2)
        self.mock_session.close.assert_called_once()

    async def test_a_get_project_report_no_issues(self):
        """Test project report retrieval with no issues."""
        project_key = "EMPTY"
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = []

        result = await self.repository.get_project_report(project_key)

        self.assertEqual(result.total_issues, 0)
        self.assertEqual(len(result.issues), 0)

    async def test_a_get_project_report_database_error(self):
        """Test project report retrieval with database error."""
        project_key = "TEST"
        
        self.mock_session.query.side_effect = Exception("Query error")

        with self.assertRaises(Exception):
            await self.repository.get_project_report(project_key)

        self.mock_session.close.assert_called_once()

    async def test_a_get_issues_by_keys_success(self):
        """Test successful issues retrieval by keys."""
        issue_keys = ["TEST-1", "TEST-2"]
        mock_tasks = [self._create_mock_task_model("TEST-1"), self._create_mock_task_model("TEST-2")]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = mock_tasks

        result = await self.repository.get_issues_by_keys(issue_keys)

        self.assertEqual(len(result), 2)
        self.mock_session.close.assert_called_once()

    async def test_a_get_issues_by_keys_empty_list(self):
        """Test issues retrieval with empty keys list."""
        result = await self.repository.get_issues_by_keys([])

        self.assertEqual(len(result), 0)
        self.mock_session.query.assert_not_called()

    async def test_a_get_issues_by_keys_database_error(self):
        """Test issues retrieval with database error."""
        issue_keys = ["TEST-1"]
        
        self.mock_session.query.side_effect = Exception("Query error")

        with self.assertRaises(Exception):
            await self.repository.get_issues_by_keys(issue_keys)

        self.mock_session.close.assert_called_once()

    def test_convert_to_model(self):
        """Test conversion from entity to model."""
        issue = JiraReportTestFactory.create_jira_issue_detail()
        
        result = self.repository._convert_to_model(issue)
        
        self.assertIsInstance(result, JiraTaskModel)
        self.assertEqual(result.key, issue.key)
        self.assertEqual(result.summary, issue.summary)
        self.assertEqual(result.task_type, issue.task_type)
        self.assertIsNotNone(result.last_synced)

    def test_convert_to_model_with_collections(self):
        """Test model conversion with worklog and linked issues."""
        issue = JiraReportTestFactory.create_jira_issue_detail(with_worklogs=True, with_linked_issues=True)
        
        result = self.repository._convert_to_model(issue)
        
        self.assertIsNotNone(result.worklog_entries)
        self.assertIsNotNone(result.linked_issues)
        self.assertIsInstance(result.worklog_entries, list)
        self.assertIsInstance(result.linked_issues, list)

    def test_convert_from_model(self):
        """Test conversion from model to entity."""
        task_model = self._create_mock_task_model("TEST-1")
        
        result = self.repository._convert_from_model(task_model)
        
        self.assertEqual(result.key, "TEST-1")
        self.assertEqual(result.summary, "Test Summary")
        self.assertEqual(result.task_type, "Story")

    def test_convert_from_model_with_none_values(self):
        """Test model conversion with None values."""
        task_model = JiraTaskModel(
            key="TEST-1",
            summary=None,
            task_type=None,
            reporter=None,
            status=None,
            created_at=None,
            updated_at=None,
        )
        
        result = self.repository._convert_from_model(task_model)
        
        self.assertEqual(result.summary, "")
        self.assertEqual(result.task_type, "")
        self.assertEqual(result.reporter, "")
        self.assertEqual(result.status, "")
        self.assertIsNotNone(result.created_at)
        self.assertIsNotNone(result.updated_at)

    def test_convert_from_model_with_collections(self):
        """Test model conversion with JSON collections."""
        task_model = self._create_mock_task_model("TEST-1")
        task_model.worklog_entries = [
            {
                "id": "12345",
                "author": "Test User",
                "time_spent": "2h",
                "time_spent_seconds": 7200,
                "created": "2025-06-27T10:00:00",
                "updated": "2025-06-27T10:30:00",
                "started": "2025-06-27T09:00:00",
                "comment": "Test worklog",
            }
        ]
        task_model.linked_issues = [
            {
                "key": "TEST-2",
                "summary": "Linked issue",
                "status": "Open",
                "issue_type": "Bug",
                "relationship": "blocks",
            }
        ]
        
        result = self.repository._convert_from_model(task_model)
        
        self.assertEqual(len(result.worklog_entries), 1)
        self.assertEqual(len(result.linked_issues), 1)
        self.assertEqual(result.worklog_entries[0].id, "12345")
        self.assertEqual(result.linked_issues[0].key, "TEST-2")

    @patch('jira_telegram_bot.adapters.repositories.jira_report_repository.urllib.parse.quote_plus')
    @patch('jira_telegram_bot.adapters.repositories.jira_report_repository.create_engine')
    def test_create_engine(self, mock_create_engine, mock_quote_plus):
        """Test database engine creation."""
        mock_quote_plus.return_value = "encoded_password"
        
        with patch.object(JiraReportRepository, '_ensure_schema_exists'):
            repository = JiraReportRepository()
        
        mock_create_engine.assert_called()
        call_args = mock_create_engine.call_args[0][0]
        self.assertIn("postgresql://", call_args)
        self.assertIn("encoded_password", call_args)

    def _create_mock_task_model(self, key: str) -> JiraTaskModel:
        """Create a mock task model for testing."""
        model = JiraTaskModel()
        model.key = key
        model.summary = "Test Summary"
        model.description = "Test Description"
        model.task_type = "Story"
        model.reporter = "Test Reporter"
        model.status = "Open"
        model.created_at = datetime(2025, 6, 27, 10, 0, 0)
        model.updated_at = datetime(2025, 6, 27, 11, 0, 0)
        model.components = ["Frontend"]
        model.labels = ["urgent"]
        model.release = ["v1.0.0"]
        model.worklog_entries = None
        model.linked_issues = None
        return model


if __name__ == "__main__":
    unittest.main()
