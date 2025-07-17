"""Unit tests for ProcessJiraEventUseCase."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from jira_telegram_bot.entities.metrics.metric_event import MetricEvent
from jira_telegram_bot.entities.metrics.constants import MetricType
from jira_telegram_bot.use_cases.metrics.process_jira_event_use_case import ProcessJiraEventUseCase


class TestProcessJiraEventUseCase(unittest.IsolatedAsyncioTestCase):
    """Test suite for ProcessJiraEventUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.metrics_processor = AsyncMock()
        self.use_case = ProcessJiraEventUseCase(self.metrics_processor)
    
    async def test_process_jira_webhook_success(self):
        """Test successful processing of Jira webhook."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "john.doe@example.com"},
                    "summary": "Test issue"
                }
            }
        }
        
        self.metrics_processor.is_event_processed.return_value = False
        self.metrics_processor.process_metric_event.return_value = True
        
        # Act
        result = await self.use_case.process_jira_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)
        self.metrics_processor.process_metric_event.assert_called_once()
        self.metrics_processor.mark_event_processed.assert_called_once()
    
    async def test_process_jira_webhook_already_processed(self):
        """Test webhook processing when event already processed."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "john.doe@example.com"}
                }
            }
        }
        
        self.metrics_processor.is_event_processed.return_value = True
        
        # Act
        result = await self.use_case.process_jira_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)
        self.metrics_processor.process_metric_event.assert_not_called()
        self.metrics_processor.mark_event_processed.assert_not_called()
    
    async def test_process_jira_webhook_missing_required_fields(self):
        """Test webhook processing with missing required fields."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"}
                    # Missing assignee
                }
            }
        }
        
        # Act
        result = await self.use_case.process_jira_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)  # Should return True even when no metric event created
        self.metrics_processor.process_metric_event.assert_not_called()
    
    def test_map_webhook_to_metric_event_issue_created(self):
        """Test mapping issue_created event to MetricEvent."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "john.doe@example.com"},
                    "summary": "Test issue",
                    "issuetype": {"name": "Story"},
                    "priority": {"name": "High"},
                    "status": {"name": "To Do"}
                }
            }
        }
        
        # Act
        result = self.use_case._map_webhook_to_metric_event(webhook_data)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.TASK_CREATED)
        self.assertEqual(result.developer_key, "john.doe@example.com")
        self.assertEqual(result.project_key, "TEST")
        self.assertEqual(result.issue_key, "TEST-123")
        self.assertEqual(result.value, 1.0)
    
    def test_map_webhook_to_metric_event_worklog(self):
        """Test mapping worklog event to MetricEvent."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "john.doe@example.com"}
                }
            },
            "worklog": {
                "timeSpentSeconds": 7200,  # 2 hours
                "author": {"emailAddress": "john.doe@example.com"},
                "comment": "Working on implementation"
            }
        }
        
        # Act
        result = self.use_case._map_webhook_to_metric_event(webhook_data)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.TIME_LOGGED)
        self.assertEqual(result.value, 2.0)  # 2 hours
        self.assertEqual(result.metadata["worklog"]["comment"], "Working on implementation")
    
    def test_map_webhook_to_metric_event_unsupported_event(self):
        """Test mapping unsupported event type."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "unsupported_event",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "john.doe@example.com"}
                }
            }
        }
        
        # Act
        result = self.use_case._map_webhook_to_metric_event(webhook_data)
        
        # Assert
        self.assertIsNone(result)
    
    def test_extract_sprint_id_success(self):
        """Test extracting sprint ID from issue data."""
        # Arrange
        issue_data = {
            "fields": {
                "customfield_10005": [
                    {"id": "123", "name": "Sprint 1"}
                ]
            }
        }
        
        # Act
        result = self.use_case._extract_sprint_id(issue_data)
        
        # Assert
        self.assertEqual(result, "123")
    
    def test_extract_sprint_id_string_format(self):
        """Test extracting sprint ID from string format."""
        # Arrange
        issue_data = {
            "fields": {
                "customfield_10005": [
                    "com.atlassian.greenhopper.service.sprint.Sprint@123[id=456,name=Sprint 1]"
                ]
            }
        }
        
        # Act
        result = self.use_case._extract_sprint_id(issue_data)
        
        # Assert
        self.assertEqual(result, "456")
    
    def test_extract_sprint_id_no_sprint(self):
        """Test extracting sprint ID when no sprint field."""
        # Arrange
        issue_data = {
            "fields": {}
        }
        
        # Act
        result = self.use_case._extract_sprint_id(issue_data)
        
        # Assert
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
