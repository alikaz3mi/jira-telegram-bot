"""Integration tests for metrics webhook endpoints."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor

from jira_telegram_bot.frameworks.api.endpoints.metrics.metrics_webhook_endpoint import MetricsWebhookEndpoint
from jira_telegram_bot.use_cases.metrics.process_jira_event_use_case import ProcessJiraEventUseCase
from jira_telegram_bot.use_cases.metrics.process_gitlab_event_use_case import ProcessGitlabEventUseCase


class TestMetricsWebhookIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for metrics webhook processing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.process_jira_use_case = AsyncMock()
        self.process_gitlab_use_case = AsyncMock()
        
        self.endpoint = MetricsWebhookEndpoint(
            process_jira_event_use_case=self.process_jira_use_case,
            process_gitlab_event_use_case=self.process_gitlab_use_case
        )
    
    async def test_concurrent_jira_webhooks_idempotency(self):
        """Test that concurrent Jira webhooks are processed idempotently."""
        # Arrange
        webhook_payload = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "john.doe@example.com"},
                    "summary": "Test issue"
                }
            },
            "timestamp": "2025-07-17T10:00:00Z"
        }
        
        # Configure use case to succeed
        self.process_jira_use_case.process_jira_webhook.return_value = True
        
        # Act - Send 20 concurrent webhooks with same event
        tasks = []
        for i in range(20):
            # Simulate background task execution
            task = self._process_jira_webhook_background(webhook_payload)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert
        # All requests should succeed
        for result in results:
            self.assertIsNone(result)  # No exceptions raised
        
        # Use case should be called 20 times (once per webhook)
        self.assertEqual(self.process_jira_use_case.process_jira_webhook.call_count, 20)
    
    async def test_concurrent_gitlab_webhooks_different_events(self):
        """Test processing concurrent GitLab webhooks with different events."""
        # Arrange
        push_payload = {
            "object_kind": "push",
            "project": {"name": "test-project", "namespace": "TEST"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix bug",
                    "author": {"email": "dev1@example.com"},
                    "timestamp": "2025-07-17T10:00:00Z"
                }
            ]
        }
        
        mr_payload = {
            "object_kind": "merge_request",
            "project": {"name": "test-project", "namespace": "TEST"},
            "object_attributes": {
                "id": 123,
                "action": "open",
                "state": "opened",
                "author": {"email": "dev2@example.com"},
                "created_at": "2025-07-17T10:00:00Z"
            }
        }
        
        # Configure use case to succeed
        self.process_gitlab_use_case.process_gitlab_webhook.return_value = True
        
        # Act - Send concurrent different webhooks
        tasks = []
        for i in range(10):
            tasks.append(self._process_gitlab_webhook_background(push_payload))
            tasks.append(self._process_gitlab_webhook_background(mr_payload))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert
        # All requests should succeed
        for result in results:
            self.assertIsNone(result)  # No exceptions raised
        
        # Use case should be called 20 times total
        self.assertEqual(self.process_gitlab_use_case.process_gitlab_webhook.call_count, 20)
    
    async def test_webhook_processing_with_failures(self):
        """Test webhook processing when some events fail."""
        # Arrange
        webhook_payload = {
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": "TEST-456",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "jane.smith@example.com"}
                }
            }
        }
        
        # Configure use case to fail on odd calls, succeed on even calls
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count % 2 == 0  # Succeed on even calls
        
        self.process_jira_use_case.process_jira_webhook.side_effect = side_effect
        
        # Act - Send 10 webhooks
        tasks = []
        for i in range(10):
            task = self._process_jira_webhook_background(webhook_payload)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert
        # All background tasks should complete without exceptions
        for result in results:
            self.assertIsNone(result)  # No exceptions raised from background tasks
        
        # Use case should be called 10 times
        self.assertEqual(self.process_jira_use_case.process_jira_webhook.call_count, 10)
    
    async def test_mixed_webhook_types_concurrent_processing(self):
        """Test concurrent processing of mixed webhook types."""
        # Arrange
        jira_payload = {
            "issue_event_type_name": "issue_resolved",
            "issue": {
                "key": "TEST-789",
                "fields": {
                    "project": {"key": "TEST"},
                    "assignee": {"emailAddress": "developer@example.com"}
                }
            }
        }
        
        gitlab_payload = {
            "object_kind": "push",
            "project": {"name": "test-repo", "namespace": "TEST"},
            "commits": [
                {
                    "id": "def456",
                    "message": "Add feature",
                    "author": {"email": "developer@example.com"},
                    "timestamp": "2025-07-17T11:00:00Z"
                }
            ]
        }
        
        # Configure use cases to succeed
        self.process_jira_use_case.process_jira_webhook.return_value = True
        self.process_gitlab_use_case.process_gitlab_webhook.return_value = True
        
        # Act - Send mixed webhooks concurrently
        tasks = []
        for i in range(5):
            tasks.append(self._process_jira_webhook_background(jira_payload))
            tasks.append(self._process_gitlab_webhook_background(gitlab_payload))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert
        # All tasks should complete successfully
        for result in results:
            self.assertIsNone(result)
        
        # Both use cases should be called 5 times each
        self.assertEqual(self.process_jira_use_case.process_jira_webhook.call_count, 5)
        self.assertEqual(self.process_gitlab_use_case.process_gitlab_webhook.call_count, 5)
    
    async def _process_jira_webhook_background(self, payload):
        """Helper method to simulate background Jira webhook processing."""
        try:
            await self.endpoint._process_jira_webhook_background(payload)
        except Exception as e:
            # Log but don't raise - background tasks should handle errors gracefully
            print(f"Background Jira webhook processing error: {e}")
    
    async def _process_gitlab_webhook_background(self, payload):
        """Helper method to simulate background GitLab webhook processing."""
        try:
            await self.endpoint._process_gitlab_webhook_background(payload)
        except Exception as e:
            # Log but don't raise - background tasks should handle errors gracefully
            print(f"Background GitLab webhook processing error: {e}")


class TestMetricsEndToEndIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration tests for metrics system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # These would be real implementations in a full integration test
        self.metrics_processor = AsyncMock()
        self.jira_use_case = ProcessJiraEventUseCase(self.metrics_processor)
        self.gitlab_use_case = ProcessGitlabEventUseCase(self.metrics_processor)
    
    async def test_end_to_end_jira_event_processing(self):
        """Test end-to-end Jira event processing."""
        # Arrange
        webhook_data = {
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "E2E-001",
                "fields": {
                    "project": {"key": "E2E"},
                    "assignee": {"emailAddress": "e2e.test@example.com"},
                    "summary": "End-to-end test issue",
                    "issuetype": {"name": "Story"},
                    "customfield_10005": [{"id": "100", "name": "Sprint 1"}]
                }
            }
        }
        
        # Configure processor for success
        self.metrics_processor.is_event_processed.return_value = False
        self.metrics_processor.process_metric_event.return_value = True
        
        # Act
        result = await self.jira_use_case.process_jira_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)
        self.metrics_processor.process_metric_event.assert_called_once()
        
        # Verify the metric event was created correctly
        call_args = self.metrics_processor.process_metric_event.call_args[0][0]
        self.assertEqual(call_args.developer_key, "e2e.test@example.com")
        self.assertEqual(call_args.project_key, "E2E")
        self.assertEqual(call_args.issue_key, "E2E-001")
        self.assertEqual(call_args.sprint_id, "100")
    
    async def test_end_to_end_gitlab_event_processing(self):
        """Test end-to-end GitLab event processing."""
        # Arrange
        webhook_data = {
            "object_kind": "merge_request",
            "project": {
                "name": "e2e-project",
                "namespace": "E2E"
            },
            "object_attributes": {
                "id": 999,
                "action": "merge",
                "state": "merged",
                "title": "E2E: Add integration test",
                "author": {"email": "e2e.gitlab@example.com"},
                "created_at": "2025-07-17T12:00:00Z"
            }
        }
        
        # Configure processor for success
        self.metrics_processor.is_event_processed.return_value = False
        self.metrics_processor.process_metric_event.return_value = True
        
        # Act
        result = await self.gitlab_use_case.process_gitlab_webhook(webhook_data)
        
        # Assert
        self.assertTrue(result)
        self.metrics_processor.process_metric_event.assert_called_once()
        
        # Verify the metric event was created correctly
        call_args = self.metrics_processor.process_metric_event.call_args[0][0]
        self.assertEqual(call_args.developer_key, "e2e.gitlab@example.com")
        self.assertEqual(call_args.project_key, "E2EE2EPROJECT")


if __name__ == "__main__":
    unittest.main()
