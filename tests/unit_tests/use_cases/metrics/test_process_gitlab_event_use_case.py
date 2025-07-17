"""Unit tests for ProcessGitlabEventUseCase."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.metrics.constants import MetricType
from jira_telegram_bot.use_cases.metrics.process_gitlab_event_use_case import ProcessGitlabEventUseCase


class TestProcessGitlabEventUseCase(unittest.IsolatedAsyncioTestCase):
    """Test suite for ProcessGitlabEventUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.metrics_processor = AsyncMock()
        self.use_case = ProcessGitlabEventUseCase(self.metrics_processor)
    
    async def test_process_gitlab_webhook_push_success(self):
        """Test successful processing of GitLab push webhook."""
        # Arrange
        webhook_data = {
            "object_kind": "push",
            "project": {
                "name": "test-project",
                "namespace": "TEST"
            },
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix bug in authentication",
                    "author": {"email": "john.doe@example.com"},
                    "timestamp": "2025-07-17T10:00:00Z",
                    "added": ["file1.py"],
                    "modified": ["file2.py"],
                    "removed": []
                }
            ],
            "ref": "refs/heads/main"
        }
        
        self.metrics_processor.is_event_processed.return_value = False
        self.metrics_processor.process_metric_event.return_value = True
        
        # Act
        result = await self.use_case.process_gitlab_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)
        self.metrics_processor.process_metric_event.assert_called_once()
        self.metrics_processor.mark_event_processed.assert_called_once()
    
    async def test_process_gitlab_webhook_merge_request_success(self):
        """Test successful processing of GitLab merge request webhook."""
        # Arrange
        webhook_data = {
            "object_kind": "merge_request",
            "project": {
                "name": "test-project",
                "namespace": "TEST"
            },
            "object_attributes": {
                "id": 123,
                "action": "open",
                "state": "opened",
                "title": "Add new feature",
                "description": "Implementing new authentication feature",
                "source_branch": "feature/auth",
                "target_branch": "main",
                "author": {"email": "jane.smith@example.com"},
                "created_at": "2025-07-17T10:00:00Z",
                "url": "https://gitlab.com/test/project/-/merge_requests/123"
            }
        }
        
        self.metrics_processor.is_event_processed.return_value = False
        self.metrics_processor.process_metric_event.return_value = True
        
        # Act
        result = await self.use_case.process_gitlab_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)
        self.metrics_processor.process_metric_event.assert_called_once()
        self.metrics_processor.mark_event_processed.assert_called_once()
    
    def test_create_commit_event_success(self):
        """Test creating a commit metric event."""
        # Arrange
        commit = {
            "id": "abc123",
            "message": "Fix authentication bug",
            "author": {"email": "john.doe@example.com"},
            "timestamp": "2025-07-17T10:00:00Z",
            "added": ["file1.py"],
            "modified": ["file2.py"],
            "removed": []
        }
        
        webhook_data = {
            "project": {
                "name": "test-project",
                "namespace": "TEST"
            },
            "ref": "refs/heads/main"
        }
        
        # Act
        result = self.use_case._create_commit_event(commit, webhook_data)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.COMMIT_MADE)
        self.assertEqual(result.developer_key, "john.doe@example.com")
        self.assertEqual(result.project_key, "TESTTESTPROJECT")
        self.assertEqual(result.value, 1.0)
        self.assertEqual(result.metadata["commit_id"], "abc123")
        self.assertEqual(result.metadata["commit_message"], "Fix authentication bug")
        self.assertEqual(result.metadata["branch"], "main")
    
    def test_create_merge_request_event_opened(self):
        """Test creating a merge request opened event."""
        # Arrange
        webhook_data = {
            "object_attributes": {
                "id": 123,
                "action": "open",
                "state": "opened",
                "title": "Add new feature",
                "description": "Implementing new feature",
                "source_branch": "feature/new",
                "target_branch": "main",
                "author": {"email": "jane.smith@example.com"},
                "created_at": "2025-07-17T10:00:00Z",
                "url": "https://gitlab.com/test/project/-/merge_requests/123"
            },
            "project": {
                "name": "test-project",
                "namespace": "TEST"
            }
        }
        
        # Act
        result = self.use_case._create_merge_request_event(webhook_data)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.MERGE_REQUEST_OPENED)
        self.assertEqual(result.developer_key, "jane.smith@example.com")
        self.assertEqual(result.metadata["merge_request_id"], 123)
        self.assertEqual(result.metadata["action"], "open")
        self.assertEqual(result.metadata["state"], "opened")
    
    def test_create_merge_request_event_merged(self):
        """Test creating a merge request merged event."""
        # Arrange
        webhook_data = {
            "object_attributes": {
                "id": 123,
                "action": "merge",
                "state": "merged",
                "title": "Add new feature",
                "author": {"email": "jane.smith@example.com"},
                "created_at": "2025-07-17T10:00:00Z"
            },
            "project": {
                "name": "test-project",
                "namespace": "TEST"
            }
        }
        
        # Act
        result = self.use_case._create_merge_request_event(webhook_data)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.MERGE_REQUEST_MERGED)
    
    def test_extract_project_key_from_gitlab_with_namespace(self):
        """Test extracting project key with namespace."""
        # Arrange
        project_info = {
            "name": "test-project",
            "namespace": "TEST"
        }
        
        # Act
        result = self.use_case._extract_project_key_from_gitlab(project_info)
        
        # Assert
        self.assertEqual(result, "TESTTESTPROJECT")
    
    def test_extract_project_key_from_gitlab_without_namespace(self):
        """Test extracting project key without namespace."""
        # Arrange
        project_info = {
            "name": "test-project"
        }
        
        # Act
        result = self.use_case._extract_project_key_from_gitlab(project_info)
        
        # Assert
        self.assertEqual(result, "TESTPROJECT")
    
    def test_map_mr_action_to_metric_open(self):
        """Test mapping MR open action to metric type."""
        # Act
        result = self.use_case._map_mr_action_to_metric("open", "opened")
        
        # Assert
        self.assertEqual(result, MetricType.MERGE_REQUEST_OPENED)
    
    def test_map_mr_action_to_metric_merge(self):
        """Test mapping MR merge action to metric type."""
        # Act
        result = self.use_case._map_mr_action_to_metric("merge", "merged")
        
        # Assert
        self.assertEqual(result, MetricType.MERGE_REQUEST_MERGED)
    
    def test_map_mr_action_to_metric_close(self):
        """Test mapping MR close action to metric type."""
        # Act
        result = self.use_case._map_mr_action_to_metric("close", "closed")
        
        # Assert
        self.assertEqual(result, MetricType.MERGE_REQUEST_CLOSED)
    
    def test_map_mr_action_to_metric_unsupported(self):
        """Test mapping unsupported MR action."""
        # Act
        result = self.use_case._map_mr_action_to_metric("unknown", "unknown")
        
        # Assert
        self.assertIsNone(result)
    
    def test_parse_gitlab_timestamp_success(self):
        """Test parsing valid GitLab timestamp."""
        # Arrange
        timestamp_str = "2025-07-17T10:00:00Z"
        
        # Act
        result = self.use_case._parse_gitlab_timestamp(timestamp_str)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertIsInstance(result, datetime)
    
    def test_parse_gitlab_timestamp_invalid(self):
        """Test parsing invalid GitLab timestamp."""
        # Arrange
        timestamp_str = "invalid-timestamp"
        
        # Act
        result = self.use_case._parse_gitlab_timestamp(timestamp_str)
        
        # Assert
        self.assertIsNone(result)
    
    def test_parse_gitlab_timestamp_none(self):
        """Test parsing None timestamp."""
        # Act
        result = self.use_case._parse_gitlab_timestamp(None)
        
        # Assert
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
