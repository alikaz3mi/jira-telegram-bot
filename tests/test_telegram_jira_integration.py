from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.services.telegram.telegram_gateway import TelegramGateway
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.telegram_commands.create_task import JiraTaskCreation


class TestTelegramJiraIntegration(unittest.TestCase):
    """Integration tests for the Telegram ↔ Jira happy path flow."""

    def setUp(self):
        """Set up test environment before each test."""
        # Mock the Jira repository
        self.jira_repository_mock = MagicMock(spec=JiraRepository)
        self.jira_repository_mock.create_task.return_value = {"key": "TEST-123"}

        # Mock user config
        self.user_config_mock = MagicMock()
        self.user_config_mock.get_user_config.return_value = MagicMock(
            jira_username="test_user",
            default_project="TEST",
            default_assignee="test_user"
        )
        
        # Set up use cases
        self.create_task_use_case = CreateTaskUseCase(self.jira_repository_mock)
        self.jira_task_creation = JiraTaskCreation(self.jira_repository_mock, self.user_config_mock)
        
        # Mock Telegram gateway
        self.telegram_gateway_mock = MagicMock(spec=TelegramGateway)
    
    def test_create_task_through_telegram(self):
        """Test creating a Jira task through Telegram command flow."""
        # Arrange
        update_mock = MagicMock()
        update_mock.effective_chat.id = 123456
        update_mock.message.from_user.username = "test_telegram_user"
        context_mock = MagicMock()
        
        # Act
        # Simulate the user starting the create task conversation
        result = self.jira_task_creation.start_conversation(update_mock, context_mock)
        
        # Assert
        # Verify the conversation was started
        self.assertTrue(result)
        # Verify user config was checked
        self.user_config_mock.get_user_config.assert_called_once_with("test_telegram_user")

    def test_create_task_use_case(self):
        """Test the core create task use case directly."""
        # Arrange
        project_key = "TEST"
        summary = "Test task summary"
        description = "Test task description"
        task_type = "Task"
        labels = ["test-label"]
        assignee = "test_user"

        # Act
        result = self.create_task_use_case.run(
            project_key=project_key,
            summary=summary,
            description=description,
            task_type=task_type,
            labels=labels,
            assignee=assignee
        )

        # Assert
        # Verify the repository was called with correct data
        expected_task_data = TaskData(
            project_key=project_key,
            summary=summary, 
            description=description,
            task_type=task_type,
            labels=labels,
            assignee=assignee
        )
        self.jira_repository_mock.create_task.assert_called_once()
        # Check the result is what we expect
        self.assertEqual(result["key"], "TEST-123")

    def test_webhook_handling(self):
        """Test handling a Jira webhook event."""
        with patch("jira_telegram_bot.use_cases.handle_jira_webhook_usecase.get_mapping_by_issue_key") as mock_get_mapping:
            # Arrange
            from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import HandleJiraWebhookUseCase
            
            mock_get_mapping.return_value = {
                "channel_chat_id": "test_channel_id",
                "group_chat_id": "test_group_id",
                "reply_message_id": 12345
            }
            
            webhook_handler = HandleJiraWebhookUseCase(self.telegram_gateway_mock)
            
            webhook_body = {
                "issue_event_type_name": "issue_created",
                "issue": {
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue summary"
                    }
                },
                "user": {
                    "displayName": "Test User"
                }
            }
            
            # Act
            webhook_handler.handle_webhook(webhook_body)
            
            # Assert
            # Verify Telegram notification was sent
            self.telegram_gateway_mock.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()