"""Integration tests for create_ticket with mock servers.

This module tests the complete create_ticket flow with mocked external services
(Telegram API and Jira API) but real FastAPI application logic.
"""
import asyncio
import json
import unittest
from typing import Any
from typing import Dict
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class MockJiraIssue:
    """Mock Jira issue object."""

    def __init__(self, key: str, summary: str = "Test Issue"):
        """Initialize mock Jira issue.

        Args:
            key: Issue key (e.g., "PCT-123")
            summary: Issue summary
        """
        self.key = key
        self.fields = Mock()
        self.fields.summary = summary
        self.fields.assignee = Mock()
        self.fields.assignee.name = "test_assignee"
        self.fields.status = Mock()
        self.fields.status.name = "To Do"


class MockJiraRepository:
    """Mock Jira repository for testing."""

    def __init__(self):
        """Initialize mock Jira repository."""
        self.issues = {}
        self.issue_counter = 1
        self.comments = {}
        self.transitions = {}

    def create_task(self, task_data: Any) -> MockJiraIssue:
        """Create a mock Jira task.

        Args:
            task_data: Task data object

        Returns:
            Mock Jira issue
        """
        issue_key = f"PCT-{self.issue_counter}"
        self.issue_counter += 1
        issue = MockJiraIssue(issue_key, task_data.summary)
        self.issues[issue_key] = {
            "summary": task_data.summary,
            "description": task_data.description,
            "assignee": task_data.assignee,
            "reporter": task_data.reporter,
            "task_type": task_data.task_type,
            "labels": task_data.labels,
        }
        return issue

    def transition_task(self, issue_key: str, transition: str):
        """Transition a task to a new status.

        Args:
            issue_key: Issue key
            transition: Transition name (e.g., "done", "review")
        """
        if issue_key in self.issues:
            self.transitions[issue_key] = transition

    def add_comment(self, issue_key: str, comment: str, username: str):
        """Add comment to an issue.

        Args:
            issue_key: Issue key
            comment: Comment text
            username: Username of commenter
        """
        if issue_key not in self.comments:
            self.comments[issue_key] = []
        self.comments[issue_key].append({"user": username, "text": comment})


class MockTelegramAPI:
    """Mock Telegram API server."""

    def __init__(self):
        """Initialize mock Telegram API."""
        self.messages_sent = []
        self.files_downloaded = {}

    def send_message(
        self, chat_id: int, text: str, reply_to_message_id: int = None
    ) -> Dict[str, Any]:
        """Mock send message.

        Args:
            chat_id: Chat ID
            text: Message text
            reply_to_message_id: Optional reply message ID

        Returns:
            Mock response
        """
        message = {
            "message_id": len(self.messages_sent) + 1,
            "chat": {"id": chat_id},
            "text": text,
            "reply_to_message_id": reply_to_message_id,
        }
        self.messages_sent.append(message)
        return {"ok": True, "result": message}

    def get_file(self, file_id: str) -> Dict[str, Any]:
        """Mock get file.

        Args:
            file_id: File ID

        Returns:
            Mock file info
        """
        return {
            "ok": True,
            "result": {"file_id": file_id, "file_path": f"files/{file_id}.jpg"},
        }

    def download_file(self, file_path: str) -> bytes:
        """Mock download file.

        Args:
            file_path: File path

        Returns:
            Mock file content
        """
        content = b"mock_file_content"
        self.files_downloaded[file_path] = content
        return content


class MockDataStore:
    """Mock data store for testing."""

    def __init__(self):
        """Initialize mock data store."""
        self.data = {}
        self.media_groups = {}

    def load_data_store(self) -> Dict[str, Any]:
        """Load data store.

        Returns:
            Data store dictionary
        """
        return self.data.copy()

    def save_data_store(self, data: Dict[str, Any]):
        """Save data store.

        Args:
            data: Data to save
        """
        self.data = data.copy()

    def save_channel_post(
        self,
        message_id: int,
        channel_chat_id: int,
        issue_key: str,
        metadata: Dict[str, Any],
    ):
        """Save channel post.

        Args:
            message_id: Message ID
            channel_chat_id: Channel chat ID
            issue_key: Jira issue key
            metadata: Additional metadata
        """
        self.data[str(message_id)] = {
            "channel_message_id": message_id,
            "channel_chat_id": channel_chat_id,
            "issue_key": issue_key,
            "metadata": metadata,
        }

    def update_group_chat_id(
        self, message_id: int, group_chat_id: int, reply_message_id: int
    ):
        """Update group chat ID.

        Args:
            message_id: Message ID
            group_chat_id: Group chat ID
            reply_message_id: Reply message ID
        """
        if str(message_id) in self.data:
            self.data[str(message_id)]["group_chat_id"] = group_chat_id
            self.data[str(message_id)]["reply_message_id"] = reply_message_id

    def find_channel_post_by_message_id(
        self, chat_id: int, message_id: int
    ) -> Dict[str, Any] | None:
        """Find channel post by message ID.

        Args:
            chat_id: Chat ID
            message_id: Message ID

        Returns:
            Channel post data or None
        """
        return self.data.get(str(message_id))

    def find_channel_post_by_issue(self, issue_key: str) -> Dict[str, Any] | None:
        """Find channel post by issue key.

        Args:
            issue_key: Jira issue key

        Returns:
            Channel post data or None
        """
        for post in self.data.values():
            if post.get("issue_key") == issue_key:
                return post
        return None

    def find_by_group_chat_and_message_id(
        self, group_chat_id: int, message_id: int
    ) -> Dict[str, Any] | None:
        """Find by group chat and message ID.

        Args:
            group_chat_id: Group chat ID
            message_id: Message ID

        Returns:
            Post data or None
        """
        for post in self.data.values():
            if (
                post.get("group_chat_id") == group_chat_id
                and post.get("reply_message_id") == message_id
            ):
                return post
        return None


class TestCreateTicketIntegration(unittest.TestCase):
    """Integration tests for create_ticket functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock instances
        self.mock_jira_repo = MockJiraRepository()
        self.mock_telegram_api = MockTelegramAPI()
        self.mock_data_store = MockDataStore()

        # Patch dependencies
        self.jira_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository",
            self.mock_jira_repo,
        )
        self.data_store_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store",
            self.mock_data_store,
        )
        self.send_message_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message",
            side_effect=self.mock_telegram_api.send_message,
        )

        self.jira_patch.start()
        self.data_store_patch.start()
        self.send_message_patch.start()

    def tearDown(self):
        """Clean up patches."""
        self.jira_patch.stop()
        self.data_store_patch.stop()
        self.send_message_patch.stop()

    @patch(
        "jira_telegram_bot.frameworks.fast_api.create_ticket.parse_jira_prompt"
    )
    async def test_handle_channel_post_creates_task(self, mock_parse):
        """Test that handling a channel post creates a Jira task."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            handle_channel_post,
        )

        # Mock AI parsing response
        mock_parse.return_value = {
            "summary": "Test Bug Report",
            "description": "AI parsed description",
            "task_type": "Bug",
            "labels": "#BUG123",
        }

        # Create channel post
        channel_post = {
            "message_id": 100,
            "chat": {"id": -1001234567890, "type": "channel"},
            "text": "Found a bug in the login page",
            "from": {"username": "test_user"},
        }

        # Handle the post
        result = await handle_channel_post(channel_post)

        # Verify task was created
        self.assertIn("issue_key", result)
        issue_key = result["issue_key"]
        self.assertTrue(issue_key.startswith("PCT-"))

        # Verify task in Jira repo
        self.assertIn(issue_key, self.mock_jira_repo.issues)
        task = self.mock_jira_repo.issues[issue_key]
        self.assertEqual(task["summary"], "Test Bug Report")
        self.assertEqual(task["task_type"], "Bug")

        # Verify data store was updated
        self.assertIn("100", self.mock_data_store.data)

    @patch(
        "jira_telegram_bot.frameworks.fast_api.create_ticket.parse_jira_prompt"
    )
    async def test_handle_media_group_creates_task_with_attachments(self, mock_parse):
        """Test handling media group creates task with attachments."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            handle_media_group_message,
        )

        # Mock AI parsing
        mock_parse.return_value = {
            "summary": "UI Screenshot Issue",
            "description": "Screenshot attached",
            "task_type": "Task",
            "labels": "#UI",
        }

        # Create media group messages
        channel_post = {
            "message_id": 200,
            "chat": {"id": -1001234567890},
            "media_group_id": "test_group_123",
            "photo": [{"file_id": "photo_123", "file_size": 12345}],
            "caption": "Screenshot of the issue",
            "from": {"username": "test_user"},
        }

        # Handle media group
        result = handle_media_group_message("test_group_123", channel_post)

        # Verify media group was registered
        self.assertEqual(result["media_group_id"], "test_group_123")

    async def test_handle_auto_forward_updates_group_chat(self):
        """Test auto-forward updates group chat ID."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            handle_auto_forward_message,
        )

        # Create existing channel post
        self.mock_data_store.save_channel_post(
            message_id=100,
            channel_chat_id=-1001234567890,
            issue_key="PCT-1",
            metadata={"creator_username": "test_user"},
        )

        # Create auto-forward message
        auto_forward_message = {
            "message_id": 300,
            "chat": {"id": -12345},  # Group chat
            "forward_from_chat": {"id": -1001234567890},  # Channel
            "forward_from_message_id": 100,
        }

        # Handle auto-forward
        result = await handle_auto_forward_message(auto_forward_message)

        # Verify result
        self.assertEqual(result["issue_key"], "PCT-1")

        # Verify message was sent to group
        self.assertTrue(len(self.mock_telegram_api.messages_sent) > 0)
        last_message = self.mock_telegram_api.messages_sent[-1]
        self.assertEqual(last_message["chat"]["id"], -12345)
        self.assertIn("PCT-1", last_message["text"])

    async def test_handle_group_comment_adds_comment_to_jira(self):
        """Test group comment adds comment to Jira issue."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            handle_group_comment,
        )

        # Create existing post with group chat info
        self.mock_data_store.data["100"] = {
            "issue_key": "PCT-1",
            "group_chat_id": -12345,
            "reply_message_id": 200,
        }

        # Create task in Jira
        from jira_telegram_bot.entities.task import TaskData

        task_data = TaskData(
            summary="Test",
            description="Test",
            task_type="Task",
            labels=["test"],
            project_key="PCT",
        )
        self.mock_jira_repo.create_task(task_data)

        # Create comment message
        comment_message = {
            "message_id": 201,
            "chat": {"id": -12345},
            "reply_to_message": {"message_id": 200},
            "text": "This is a comment on the task",
            "from": {"username": "commenter"},
        }

        # Handle comment
        result = await handle_group_comment(comment_message)

        # Verify comment was added
        self.assertEqual(result["issue_key"], "PCT-1")
        self.assertIn("PCT-1", self.mock_jira_repo.comments)
        comments = self.mock_jira_repo.comments["PCT-1"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["text"], "This is a comment on the task")

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    async def test_process_done_command_transitions_task(self, mock_user_config):
        """Test /done command transitions task to done."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            process_command,
        )

        # Setup user config
        mock_user = Mock()
        mock_user.jira_username = "test_jira_user"
        mock_user_config.get_user_config.return_value = mock_user

        # Create task and post
        from jira_telegram_bot.entities.task import TaskData

        task_data = TaskData(
            summary="Test Task",
            description="Test",
            task_type="Task",
            labels=["test"],
            project_key="PCT",
        )
        issue = self.mock_jira_repo.create_task(task_data)

        self.mock_data_store.data[str(issue.key)] = {
            "issue_key": issue.key,
            "group_chat_id": -12345,
            "reply_message_id": 100,
            "metadata": {"creator_username": "test_user"},
        }

        # Process /done command
        result = await process_command(
            "/done", issue.key, "test_user", "test_jira_user"
        )

        # Verify transition
        self.assertEqual(result["status"], "success")
        self.assertIn(issue.key, self.mock_jira_repo.transitions)
        self.assertEqual(self.mock_jira_repo.transitions[issue.key], "done")

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    async def test_process_review_command_transitions_task(self, mock_user_config):
        """Test /review command transitions task to review."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            process_command,
        )

        # Setup user config and Jira issue
        mock_user = Mock()
        mock_user.jira_username = "test_assignee"
        mock_user_config.get_user_config.return_value = mock_user

        # Create task
        from jira_telegram_bot.entities.task import TaskData

        task_data = TaskData(
            summary="Test Task",
            description="Test",
            task_type="Task",
            labels=["test"],
            project_key="PCT",
            assignee="test_assignee",
        )
        issue = self.mock_jira_repo.create_task(task_data)

        self.mock_data_store.data[str(issue.key)] = {
            "issue_key": issue.key,
            "group_chat_id": -12345,
            "reply_message_id": 100,
        }

        # Mock Jira issue retrieval
        self.mock_jira_repo.jira = Mock()
        self.mock_jira_repo.jira.issue.return_value = MockJiraIssue(
            issue.key, "Test Task"
        )

        # Process /review command
        result = await process_command(
            "/review", issue.key, "test_user", "test_assignee"
        )

        # Verify transition
        self.assertEqual(result["status"], "success")
        self.assertIn(issue.key, self.mock_jira_repo.transitions)
        self.assertEqual(self.mock_jira_repo.transitions[issue.key], "review")

    def test_get_user_assignee_and_reporter_with_valid_user(self):
        """Test get_user_assignee_and_reporter with valid user."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            get_user_assignee_and_reporter,
        )

        with patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.user_config"
        ) as mock_config:
            mock_user = Mock()
            mock_user.jira_username = "valid_jira_user"
            mock_config.get_user_config.return_value = mock_user

            assignee, reporter = get_user_assignee_and_reporter("valid_telegram_user")

            self.assertEqual(assignee, "valid_jira_user")
            self.assertEqual(reporter, "valid_jira_user")

    def test_get_user_assignee_and_reporter_with_invalid_user(self):
        """Test get_user_assignee_and_reporter with invalid user."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            get_user_assignee_and_reporter,
        )

        with patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.user_config"
        ) as mock_config:
            mock_config.get_user_config.return_value = None

            assignee, reporter = get_user_assignee_and_reporter("invalid_user")

            self.assertIsNone(assignee)
            self.assertIsNone(reporter)

    def test_create_task_data_with_full_description(self):
        """Test create_task_data with both original and parsed descriptions."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            create_task_data,
        )

        with patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.get_user_assignee_and_reporter",
            return_value=("jira_user", "jira_user"),
        ):
            parsed_fields = {
                "summary": "Test Task",
                "description": "AI parsed description",
                "task_type": "Task",
                "labels": "#TEST",
            }
            original_text = "Original user message"

            task_data = create_task_data("test_user", parsed_fields, original_text)

            self.assertEqual(task_data.summary, "Test Task")
            self.assertIn("Original Message from User", task_data.description)
            self.assertIn("Original user message", task_data.description)
            self.assertIn("AI Analysis", task_data.description)
            self.assertIn("AI parsed description", task_data.description)

    def test_format_jalali_date_with_valid_date(self):
        """Test format_jalali_date with valid Gregorian date."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            format_jalali_date,
        )

        result = format_jalali_date("2024-03-20 12:00")

        # March 20, 2024 is Persian New Year (1403/01/01)
        self.assertIn("1403", result)
        self.assertIn("12:00", result)


class TestCreateTicketWebhookIntegration(unittest.TestCase):
    """Integration tests for webhook endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repo = MockJiraRepository()
        self.mock_data_store = MockDataStore()
        self.mock_telegram_api = MockTelegramAPI()

        self.jira_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository",
            self.mock_jira_repo,
        )
        self.data_store_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store",
            self.mock_data_store,
        )
        self.send_message_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message",
            side_effect=self.mock_telegram_api.send_message,
        )

        self.jira_patch.start()
        self.data_store_patch.start()
        self.send_message_patch.start()

    def tearDown(self):
        """Clean up patches."""
        self.jira_patch.stop()
        self.data_store_patch.stop()
        self.send_message_patch.stop()

    @patch("jira_telegram_bot.frameworks.fast_api.create_ticket.user_config")
    async def test_jira_webhook_assignee_notification(self, mock_user_config):
        """Test Jira webhook sends notification when assignee is set."""
        from jira_telegram_bot.frameworks.fast_api.create_ticket import (
            jira_webhook_endpoint,
        )
        from fastapi import Request

        # Setup user config
        mock_user = Mock()
        mock_user.telegram_id = 123456
        mock_user.jira_username = "assignee_user"
        mock_user_config.get_user_by_jira_username.return_value = mock_user

        # Create task and post
        from jira_telegram_bot.entities.task import TaskData

        task_data = TaskData(
            summary="Test Task",
            description="Test",
            task_type="Task",
            labels=["test"],
            project_key="PCT",
        )
        issue = self.mock_jira_repo.create_task(task_data)

        self.mock_data_store.data[str(issue.key)] = {
            "issue_key": issue.key,
            "group_chat_id": -12345,
            "reply_message_id": 100,
        }

        # Create webhook payload
        webhook_data = {
            "webhookEvent": "jira:issue_updated",
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": issue.key,
                "fields": {
                    "summary": "Test Task",
                    "assignee": {"name": "assignee_user"},
                },
            },
            "changelog": {
                "items": [{"field": "assignee", "toString": "assignee_user"}]
            },
        }

        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.json = AsyncMock(return_value=webhook_data)

        # Handle webhook
        result = await jira_webhook_endpoint(mock_request)

        # Verify notifications were sent
        self.assertEqual(result["status"], "success")
        self.assertTrue(len(self.mock_telegram_api.messages_sent) >= 1)

        # Check that direct message was sent to assignee
        direct_messages = [
            msg
            for msg in self.mock_telegram_api.messages_sent
            if msg["chat"]["id"] == 123456
        ]
        self.assertTrue(len(direct_messages) > 0)


if __name__ == "__main__":
    unittest.main()
