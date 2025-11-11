"""End-to-end tests for create_ticket FastAPI endpoints.

This module tests the complete FastAPI application with TestClient,
simulating real HTTP requests to the webhook endpoints.
"""
import asyncio
import json
import unittest
from typing import Any
from typing import Dict
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class MockJiraServer:
    """Mock Jira server for E2E testing."""

    def __init__(self):
        """Initialize mock Jira server."""
        self.issues = {}
        self.issue_counter = 1
        self.comments = {}
        self.transitions_log = []

    def create_issue(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Create an issue.

        Args:
            fields: Issue fields

        Returns:
            Created issue data
        """
        issue_key = f"PCT-{self.issue_counter}"
        self.issue_counter += 1

        issue = {
            "key": issue_key,
            "fields": fields,
            "id": str(self.issue_counter * 1000),
        }
        self.issues[issue_key] = issue
        return issue

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get issue by key.

        Args:
            issue_key: Issue key

        Returns:
            Issue data
        """
        return self.issues.get(issue_key)

    def transition_issue(self, issue_key: str, transition_id: str):
        """Transition an issue.

        Args:
            issue_key: Issue key
            transition_id: Transition ID
        """
        self.transitions_log.append({"issue_key": issue_key, "transition": transition_id})

    def add_comment(self, issue_key: str, body: str):
        """Add comment to issue.

        Args:
            issue_key: Issue key
            body: Comment body
        """
        if issue_key not in self.comments:
            self.comments[issue_key] = []
        self.comments[issue_key].append({"body": body})


class MockTelegramServer:
    """Mock Telegram server for E2E testing."""

    def __init__(self):
        """Initialize mock Telegram server."""
        self.messages = []
        self.files = {}
        self.message_counter = 1000

    def send_message(
        self, chat_id: int, text: str, reply_to_message_id: int = None
    ) -> Dict[str, Any]:
        """Send a message.

        Args:
            chat_id: Chat ID
            text: Message text
            reply_to_message_id: Optional reply message ID

        Returns:
            Message data
        """
        message = {
            "message_id": self.message_counter,
            "chat": {"id": chat_id, "type": "group" if chat_id < 0 else "private"},
            "text": text,
            "date": 1234567890,
        }
        if reply_to_message_id:
            message["reply_to_message"] = {"message_id": reply_to_message_id}

        self.messages.append(message)
        self.message_counter += 1
        return message

    def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file info.

        Args:
            file_id: File ID

        Returns:
            File info
        """
        return {
            "file_id": file_id,
            "file_unique_id": f"unique_{file_id}",
            "file_size": 12345,
            "file_path": f"photos/{file_id}.jpg",
        }

    def download_file(self, file_path: str) -> bytes:
        """Download file.

        Args:
            file_path: File path

        Returns:
            File content
        """
        return b"mock_file_content_" + file_path.encode()


@pytest.mark.asyncio
class TestCreateTicketE2E(unittest.TestCase):
    """End-to-end tests for create_ticket endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up class fixtures."""
        cls.mock_jira = MockJiraServer()
        cls.mock_telegram = MockTelegramServer()

    def setUp(self):
        """Set up test fixtures."""
        # Reset mock servers
        self.mock_jira.issues.clear()
        self.mock_jira.comments.clear()
        self.mock_jira.transitions_log.clear()
        self.mock_jira.issue_counter = 1

        self.mock_telegram.messages.clear()
        self.mock_telegram.message_counter = 1000

        # Setup patches
        self.setup_patches()

        # Import app after patches are in place
        from jira_telegram_bot.frameworks.fast_api.create_ticket import app

        self.client = TestClient(app)

    def setup_patches(self):
        """Setup all necessary patches."""
        # Patch Jira repository
        self.jira_create_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository.create_task"
        )
        self.jira_transition_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository.transition_task"
        )
        self.jira_comment_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository.add_comment"
        )
        self.jira_jira_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository.jira"
        )

        # Patch Telegram
        self.telegram_send_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message"
        )

        # Patch data store
        self.data_store_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.telegram_post_data_store"
        )

        # Patch AI parsing
        self.parse_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.parse_jira_prompt"
        )

        # Patch user config
        self.user_config_patch = patch(
            "jira_telegram_bot.frameworks.fast_api.create_ticket.user_config"
        )

        # Start patches
        mock_jira_create = self.jira_create_patch.start()
        mock_jira_transition = self.jira_transition_patch.start()
        mock_jira_comment = self.jira_comment_patch.start()
        self.mock_jira_jira = self.jira_jira_patch.start()
        mock_telegram_send = self.telegram_send_patch.start()
        self.mock_data_store = self.data_store_patch.start()
        self.mock_parse = self.parse_patch.start()
        self.mock_user_config = self.user_config_patch.start()

        # Configure mocks
        def create_task_side_effect(task_data):
            issue_dict = self.mock_jira.create_issue(
                {
                    "summary": task_data.summary,
                    "description": task_data.description,
                    "issuetype": {"name": task_data.task_type},
                    "assignee": {"name": task_data.assignee} if task_data.assignee else None,
                    "reporter": {"name": task_data.reporter} if task_data.reporter else None,
                }
            )
            mock_issue = Mock()
            mock_issue.key = issue_dict["key"]
            mock_issue.fields = Mock()
            mock_issue.fields.summary = task_data.summary
            mock_issue.fields.assignee = Mock()
            mock_issue.fields.assignee.name = task_data.assignee if task_data.assignee else None
            return mock_issue

        mock_jira_create.side_effect = create_task_side_effect
        mock_jira_transition.side_effect = lambda key, trans: self.mock_jira.transition_issue(
            key, trans
        )
        mock_jira_comment.side_effect = lambda key, body, user=None: self.mock_jira.add_comment(
            key, body
        )
        
        # Mock jira.issue() method
        def mock_issue_lookup(issue_key):
            issue_data = self.mock_jira.get_issue(issue_key)
            if issue_data:
                mock_issue = Mock()
                mock_issue.key = issue_key
                mock_issue.fields = Mock()
                mock_issue.fields.summary = issue_data["fields"].get("summary", "Test")
                assignee_data = issue_data["fields"].get("assignee")
                if assignee_data:
                    mock_issue.fields.assignee = Mock()
                    mock_issue.fields.assignee.name = assignee_data.get("name")
                else:
                    mock_issue.fields.assignee = None
                    # Ensure we can still get .name safely - return None when accessed
                    mock_assignee = Mock()
                    mock_assignee.name = None
                    mock_issue.fields.assignee = mock_assignee
                return mock_issue
            raise Exception(f"Issue {issue_key} not found")
        
        self.mock_jira_jira.issue.side_effect = mock_issue_lookup
        
        mock_telegram_send.side_effect = lambda chat_id, text, **kwargs: (
            self.mock_telegram.send_message(
                chat_id, text, reply_to_message_id=kwargs.get("reply_message_id")
            )
        )

        # Configure data store mock
        self.mock_data_store.load_data_store.return_value = {}
        self.mock_data_store.save_data_store.side_effect = lambda x: None
        self.mock_data_store.save_channel_post.side_effect = lambda *args, **kwargs: None
        self.mock_data_store.find_channel_post_by_message_id.return_value = None
        self.mock_data_store.find_channel_post_by_issue.return_value = None
        self.mock_data_store.find_by_group_chat_and_message_id.return_value = None
        self.mock_data_store.find_issue_key_from_message_id.return_value = None
        
        # Mock async methods
        self.mock_data_store.save_mapping = AsyncMock()
        self.mock_data_store.update_group_chat_id = AsyncMock()

        # Configure AI parsing mock
        self.mock_parse.return_value = {
            "summary": "Test Issue from E2E",
            "description": "AI analyzed description",
            "task_type": "Task",
            "labels": "#TEST",
        }

        # Configure user config mock
        mock_user = Mock()
        mock_user.jira_username = "test_user"
        mock_user.telegram_id = 123456
        self.mock_user_config.get_user_config.return_value = mock_user
        self.mock_user_config.get_user_by_jira_username.return_value = mock_user

    def tearDown(self):
        """Clean up patches."""
        self.jira_create_patch.stop()
        self.jira_transition_patch.stop()
        self.jira_comment_patch.stop()
        self.telegram_send_patch.stop()
        self.data_store_patch.stop()
        self.parse_patch.stop()
        self.user_config_patch.stop()

    def test_telegram_webhook_channel_post(self):
        """Test telegram webhook receives channel post and creates task."""
        webhook_payload = {
            "update_id": 123456,
            "channel_post": {
                "message_id": 100,
                "chat": {"id": -1001234567890, "type": "channel", "title": "Test Channel"},
                "date": 1234567890,
                "text": "Bug: Login page is broken",
                "from": {"id": 111, "username": "test_user", "first_name": "Test"},
            },
        }

        response = self.client.post("/webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "Single message processed, Jira created.")

        # Verify issue was created in mock Jira
        self.assertEqual(len(self.mock_jira.issues), 1)

    def test_telegram_webhook_media_group(self):
        """Test telegram webhook handles media group."""
        webhook_payload = {
            "update_id": 123457,
            "channel_post": {
                "message_id": 200,
                "chat": {"id": -1001234567890, "type": "channel"},
                "date": 1234567890,
                "media_group_id": "test_media_group_123",
                "photo": [
                    {"file_id": "photo_abc123", "file_size": 50000, "width": 1280, "height": 720}
                ],
                "caption": "Screenshot of the error",
                "from": {"id": 111, "username": "test_user"},
            },
        }

        response = self.client.post("/webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "Media group update stored. Awaiting more.")

    def test_telegram_webhook_auto_forward(self):
        """Test telegram webhook handles auto-forwarded message."""
        # First create an issue in mock Jira
        issue = self.mock_jira.create_issue({
            "summary": "Test Task",
            "description": "Test Description",
            "issuetype": {"name": "Task"},
        })
        
        # Setup existing channel post in data store
        self.mock_data_store.find_channel_post_by_message_id.return_value = {
            "channel_message_id": 100,
            "issue_key": issue["key"],
            "channel_chat_id": -1001234567890,
        }

        webhook_payload = {
            "update_id": 123458,
            "message": {
                "message_id": 300,
                "chat": {"id": -12345, "type": "group"},
                "date": 1234567890,
                "forward_from_chat": {"id": -1001234567890, "type": "channel"},
                "forward_from_message_id": 100,
                "forward_date": 1234567880,
                "text": "Forwarded message",
            },
        }

        response = self.client.post("/webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")

    def test_telegram_webhook_group_comment(self):
        """Test telegram webhook handles comment in group."""
        # First create an issue in mock Jira
        issue = self.mock_jira.create_issue({
            "summary": "Test Task",
            "description": "Test Description",
            "issuetype": {"name": "Task"},
        })
        
        # Setup data store to return this issue key
        self.mock_data_store.find_issue_key_from_message_id.return_value = issue["key"]

        webhook_payload = {
            "update_id": 123459,
            "message": {
                "message_id": 201,
                "chat": {"id": -12345, "type": "group"},
                "date": 1234567890,
                "reply_to_message": {"message_id": 200, "forward_from_message_id": 100},
                "text": "Great job on this task!",
                "from": {"id": 222, "username": "reviewer"},
            },
        }

        response = self.client.post("/webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")

        # Verify comment was added
        self.assertIn(issue["key"], self.mock_jira.comments)

        # Verify comment was added
        self.assertIn("PCT-1", self.mock_jira.comments)

    def test_telegram_webhook_done_command(self):
        """Test telegram webhook handles /done command."""
        # First create an issue in mock Jira
        issue = self.mock_jira.create_issue({
            "summary": "Test Task",
            "description": "Test Description",
            "issuetype": {"name": "Task"},
        })
        
        # Setup data store to return this issue key
        self.mock_data_store.find_issue_key_from_message_id.return_value = issue["key"]
        
        # Setup find_channel_post_by_issue to return proper metadata
        self.mock_data_store.find_channel_post_by_issue.return_value = {
            "issue_key": issue["key"],
            "group_chat_id": -12345,
            "reply_message_id": 100,
            "metadata": {
                "creator_username": "test_user"  # Must match the webhook sender
            }
        }

        webhook_payload = {
            "update_id": 123460,
            "message": {
                "message_id": 202,
                "chat": {"id": -12345, "type": "group"},
                "date": 1234567890,
                "reply_to_message": {"message_id": 200, "forward_from_message_id": 100},
                "text": "/done",
                "from": {"id": 111, "username": "test_user"},
            },
        }

        response = self.client.post("/webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")

        # Verify transition was logged
        transitions = [t for t in self.mock_jira.transitions_log if t["issue_key"] == issue["key"]]
        self.assertTrue(len(transitions) > 0)

    def test_jira_webhook_assignee_change(self):
        """Test Jira webhook handles assignee change."""
        # First create an issue in mock Jira
        issue = self.mock_jira.create_issue({
            "summary": "Test Issue",
            "description": "Test Description",
            "issuetype": {"name": "Task"},
            "assignee": None,
        })
        
        # Setup existing task in data store
        self.mock_data_store.find_channel_post_by_issue.return_value = {
            "issue_key": issue["key"],
            "group_chat_id": -12345,
            "reply_message_id": 100,
        }

        webhook_payload = {
            "webhookEvent": "jira:issue_updated",
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": issue["key"],
                "fields": {
                    "summary": "Test Issue",
                    "assignee": {"name": "new_assignee", "displayName": "New Assignee"},
                },
            },
            "changelog": {
                "items": [
                    {
                        "field": "assignee",
                        "fromString": None,
                        "toString": "new_assignee",
                    }
                ]
            },
        }

        response = self.client.post("/jira-webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")
        # Webhook processed successfully - notification would be sent in real scenario

    def test_jira_webhook_status_change(self):
        """Test Jira webhook handles status change."""
        self.mock_data_store.find_channel_post_by_issue.return_value = {
            "issue_key": "PCT-2",
            "group_chat_id": -12345,
            "reply_message_id": 101,
        }

        webhook_payload = {
            "webhookEvent": "jira:issue_updated",
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": "PCT-2",
                "fields": {"summary": "Test Issue", "status": {"name": "In Progress"}},
            },
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "To Do",
                        "toString": "In Progress",
                    }
                ]
            },
        }

        response = self.client.post("/jira-webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)

    def test_jira_webhook_comment_added(self):
        """Test Jira webhook handles comment added."""
        self.mock_data_store.find_channel_post_by_issue.return_value = {
            "issue_key": "PCT-3",
            "group_chat_id": -12345,
            "reply_message_id": 102,
        }

        webhook_payload = {
            "webhookEvent": "comment_created",
            "comment": {
                "body": "This is a Jira comment",
                "author": {"name": "jira_user", "displayName": "Jira User"},
            },
            "issue": {
                "key": "PCT-3",
                "fields": {"summary": "Test Issue"},
            },
        }

        response = self.client.post("/jira-webhook", json=webhook_payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")

    def test_complete_flow_channel_to_group_to_done(self):
        """Test complete flow: channel post → auto-forward → comment → done."""
        # Step 1: Channel post creates task
        channel_post_payload = {
            "update_id": 1,
            "channel_post": {
                "message_id": 100,
                "chat": {"id": -1001234567890, "type": "channel"},
                "date": 1234567890,
                "text": "New feature request",
                "from": {"id": 111, "username": "requester"},
            },
        }

        response1 = self.client.post("/webhook", json=channel_post_payload)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.json()["status"], "success")
        
        # Get the created issue key from mock Jira
        self.assertEqual(len(self.mock_jira.issues), 1)
        issue_key = list(self.mock_jira.issues.keys())[0]

        # Step 2: Setup for auto-forward
        self.mock_data_store.find_channel_post_by_message_id.return_value = {
            "channel_message_id": 100,
            "issue_key": issue_key,
            "channel_chat_id": -1001234567890,
        }

        auto_forward_payload = {
            "update_id": 2,
            "message": {
                "message_id": 300,
                "chat": {"id": -12345, "type": "group"},
                "date": 1234567891,
                "forward_from_chat": {"id": -1001234567890},
                "forward_from_message_id": 100,
            },
        }

        response2 = self.client.post("/webhook", json=auto_forward_payload)
        self.assertEqual(response2.status_code, 200)

        # Step 3: Comment on task
        self.mock_data_store.find_issue_key_from_message_id.return_value = issue_key

        comment_payload = {
            "update_id": 3,
            "message": {
                "message_id": 301,
                "chat": {"id": -12345, "type": "group"},
                "date": 1234567892,
                "reply_to_message": {"message_id": 300, "forward_from_message_id": 100},
                "text": "Working on it!",
                "from": {"id": 111, "username": "requester"},
            },
        }

        response3 = self.client.post("/webhook", json=comment_payload)
        self.assertEqual(response3.status_code, 200)

        # Step 4: Mark as done
        # Setup find_channel_post_by_issue for command processing
        self.mock_data_store.find_channel_post_by_issue.return_value = {
            "issue_key": issue_key,
            "group_chat_id": -12345,
            "reply_message_id": 300,
            "metadata": {"creator_username": "requester"},
        }

        done_payload = {
            "update_id": 4,
            "message": {
                "message_id": 302,
                "chat": {"id": -12345, "type": "group"},
                "date": 1234567893,
                "reply_to_message": {"message_id": 300, "forward_from_message_id": 100},
                "text": "/done",
                "from": {"id": 111, "username": "requester"},
            },
        }

        response4 = self.client.post("/webhook", json=done_payload)
        self.assertEqual(response4.status_code, 200)
        self.assertEqual(response4.json()["status"], "success")

        # Verify the issue was transitioned
        transitions = [
            t for t in self.mock_jira.transitions_log if t["issue_key"] == issue_key
        ]
        self.assertTrue(len(transitions) > 0)
        self.assertEqual(transitions[0]["transition"], "done")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
