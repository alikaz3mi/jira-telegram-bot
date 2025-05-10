from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Message
from telegram import Update
from telegram import User
from telegram.ext import CallbackContext

from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.entities.field_config import FieldConfig
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.create_easy_task import JiraEasyTaskCreation
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot import DEFAULT_PATH


class TestJiraEasyTaskCreation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Mock the Jira client
        self.jira_client = MagicMock(spec=TaskManagerRepositoryInterface)
        self.jira_client.get_projects.return_value = [
            MagicMock(name="Project A", key="PA"),
            MagicMock(name="Project B", key="PB"),
        ]
        self.jira_client.get_epics.return_value = [
            MagicMock(key="EPIC-1"),
            MagicMock(key="EPIC-2"),
        ]
        self.jira_client.get_boards.return_value = [
            MagicMock(id=1, name="Board PA"),
            MagicMock(id=2, name="Board PB"),
        ]
        self.jira_client.get_sprints.return_value = [
            MagicMock(id=101, name="Sprint 1", state="active"),
            MagicMock(id=102, name="Sprint 2", state="future"),
        ]
        self.jira_client.get_project_components.return_value = [
            MagicMock(name="Component X"),
            MagicMock(name="Component Y"),
        ]
        self.jira_client.get_project_versions.return_value = [
            MagicMock(name="Version 1.0", released=False),
            MagicMock(name="Version 2.0", released=False),
        ]
        self.jira_client.create_issue.return_value = MagicMock(
            permalink=lambda: "http://jira.example.com/browse/ISSUE-1",
        )
        self.jira_client.add_attachment = MagicMock()
        self.user_allowed = AsyncMock(True)

        # Mock the user config
        self.user_config_instance = MagicMock(spec=UserConfig)
        self.user_config_instance.get_user_config.return_value = MagicMock(
            telegram_username="testuser",
            jira_username="jirauser",
            project=MagicMock(set_field=False, values=["PA"]),
            component=MagicMock(set_field=True, values=["Component X", "Component Y"]),
            task_type=MagicMock(set_field=True, values=["Bug", "Task"]),
            story_point=MagicMock(set_field=True, values=None),
            attachment=MagicMock(set_field=True, values=None),
            epic_link=MagicMock(set_field=True, values=None),
            release=MagicMock(set_field=True, values=None),
            sprint=MagicMock(set_field=True, values=None),
        )

        # Get user config dictionary
        self.user_config_dict = (
            self.user_config_instance.get_user_config.return_value.dict()
        )

        # Mock the logger
        self.logger = MagicMock()

        # Initialize the JiraEasyTaskCreation instance
        self.task_creation = JiraEasyTaskCreation(
            jira_client=self.jira_client,
            user_config_instance=self.user_config_instance,
            logger=self.logger,
        )

        # Mock the Update and Context
        self.user = User(
            id=123456,
            is_bot=False,
            first_name="Test",
            username="testuser",
        )
        self.message = MagicMock(spec=Message)
        self.message.from_user = self.user
        self.message.reply_text = AsyncMock()
        self.update = MagicMock(spec=Update)
        self.update.message = self.message
        self.context = MagicMock(spec=CallbackContext)
        self.context.user_data = {}

    @patch('jira_telegram_bot.use_cases.create_easy_task.check_user_allowed', new_callable=AsyncMock)
    async def test_start_with_user_config_project(self, mock_check_user_allowed):
        mock_check_user_allowed.return_value = True
        # Test the start method when user_config provides a project
        await self.task_creation.start(self.update, self.context)
        # Should proceed to ask for summary
        task_data = self.context.user_data["task_data"]
        self.assertEqual(
            task_data.project_key,
            "PA",
        )
        self.message.reply_text.assert_called_with("Please enter the task summary:", reply_markup=None)

    @patch('jira_telegram_bot.use_cases.create_easy_task.check_user_allowed', new_callable=AsyncMock)
    async def test_start_without_user_config_project(self, mock_check_user_allowed):
        mock_check_user_allowed.return_value = True
        # Modify user_config to not provide a project
        self.user_config_instance.get_user_config.return_value.project.values = []
        self.user_config_dict = (
            self.user_config_instance.get_user_config.return_value.dict()
        )
        await self.task_creation.start(self.update, self.context)
        # Should ask for project selection
        self.message.reply_text.assert_called_with(
            "Please select a project:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text="", callback_data="PA"),
                        InlineKeyboardButton(text="", callback_data="PB"),
                    ]
                ]
            )
        )

    async def test_add_project(self):
        # Simulate user selecting a project
        query = MagicMock()
        query.data = "PA"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict

        await self.task_creation.add_project(self.update, self.context)

        self.assertEqual(self.context.user_data["task_data"].project_key, "PA")
        query.message.edit_text.assert_called_with("Please enter the task summary:")

    async def test_add_summary(self):
        # Simulate user entering a summary
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.context.user_data["task_data"].project_key = "PA"  # Ensure project_key is set
        self.update.message.text = "This is a test summary."
        await self.task_creation.add_summary(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].summary,
            "This is a test summary.",
        )
        self.message.reply_text.assert_called_with(
            "Please enter the task description (or type 'skip' to skip):",
        )

    async def test_add_description(self):
        # Simulate user entering a description
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.context.user_data["task_data"].project_key = "PA"  # Ensure project_key is set
        self.update.message.text = "This is a test description."
        await self.task_creation.add_description(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].description,
            "This is a test description.",
        )
        # Should proceed to handle component selection
        self.message.reply_text.assert_called_with(
            "Select a component:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Component X",
                            callback_data="Component X",
                        ),
                        InlineKeyboardButton(
                            "Component Y",
                            callback_data="Component Y",
                        ),
                    ],
                    [InlineKeyboardButton("Skip", callback_data="skip")],
                ],
            ),
        )

    async def test_add_component(self):
        # Simulate user selecting a component
        query = MagicMock()
        query.data = "Component X"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict

        await self.task_creation.handle_component_selection(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].component,
            "Component X",
        )
        query.message.edit_text.assert_called_with(
            "Select a task type:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("", callback_data="Bug"),
                        InlineKeyboardButton("", callback_data="Task"),
                    ],
                    [InlineKeyboardButton("", callback_data="skip")],
                ],
            )
        )

    async def test_add_task_type(self):
        # Simulate user selecting a task type
        query = MagicMock()
        query.data = "Bug"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict

        await self.task_creation.add_task_type(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].task_type,
            "Bug",
        )
        query.message.edit_text.assert_called_with(
            "Select story points:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("0.5", callback_data="0.5"),
                        InlineKeyboardButton("1", callback_data="1"),
                        InlineKeyboardButton("1.5", callback_data="1.5"),
                    ],
                    [
                        InlineKeyboardButton("2", callback_data="2"),
                        InlineKeyboardButton("3", callback_data="3"),
                        InlineKeyboardButton("5", callback_data="5"),
                    ],
                    [
                        InlineKeyboardButton("8", callback_data="8"),
                        InlineKeyboardButton("13", callback_data="13"),
                        InlineKeyboardButton("21", callback_data="21"),
                    ],
                    [InlineKeyboardButton("Skip", callback_data="skip")],
                ],
            ),
        )

    async def test_add_story_points(self):
        # Simulate user selecting story points
        query = MagicMock()
        query.data = "5"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.context.user_data["task_data"].board_id = 1

        await self.task_creation.add_story_points(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].story_points,
            5.0,
        )
        # Should proceed to ask for sprint
        query.message.edit_text.assert_called_with(
            "Choose a sprint from the list below:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Sprint 1", callback_data="101"),
                        InlineKeyboardButton("Sprint 2", callback_data="102"),
                    ],
                    [InlineKeyboardButton("Skip", callback_data="skip")],
                ],
            ),
        )

    async def test_add_sprint(self):
        # Simulate user selecting a sprint
        query = MagicMock()
        query.data = "101"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.context.user_data["task_data"].board_id = 1
        self.context.user_data[
            "task_data"
        ].epics = self.jira_client.get_epics.return_value

        await self.task_creation.add_sprint(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].sprint_id,
            101,
        )
        # Should proceed to ask for epic link
        query.message.edit_text.assert_called_with(
            "Select an Epic Link:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("EPIC-1", callback_data="EPIC-1"),
                        InlineKeyboardButton("EPIC-2", callback_data="EPIC-2"),
                    ],
                    [InlineKeyboardButton("Skip", callback_data="skip")],
                ],
            ),
        )

    async def test_add_epic_link(self):
        # Simulate user selecting an epic link
        query = MagicMock()
        query.data = "EPIC-1"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.context.user_data[
            "task_data"
        ].epics = self.jira_client.get_epics.return_value

        await self.task_creation.add_epic_link(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].epic_link,
            "EPIC-1",
        )
        # Should proceed to ask for release
        query.message.edit_text.assert_called_with(
            "Select a Release:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Version 1.0",
                            callback_data="Version 1.0",
                        ),
                        InlineKeyboardButton(
                            "Version 2.0",
                            callback_data="Version 2.0",
                        ),
                    ],
                    [InlineKeyboardButton("Skip", callback_data="skip")],
                ],
            ),
        )

    async def test_add_release(self):
        # Simulate user selecting a release
        query = MagicMock()
        query.data = "Version 1.0"
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        query.message.reply_text = AsyncMock()
        self.update.callback_query = query
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict

        await self.task_creation.add_release(self.update, self.context)

        self.assertEqual(
            self.context.user_data["task_data"].release,
            "Version 1.0",
        )
        # Should proceed to ask for attachment
        query.message.edit_text.assert_called_with(
            "Please upload any attachments. When you are done, type 'done'.\nIf you wish to skip attachments, type 'skip'.",
        )

    async def test_add_attachment_skip(self):
        # Simulate user typing 'skip' for attachments
        self.update.message.text = "skip"
        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.update.message.reply_text = AsyncMock()

        await self.task_creation.add_attachment(self.update, self.context)

        # Should proceed to finalize task
        self.jira_client.create_issue.assert_called()
        self.update.message.reply_text.assert_called_with(
            f"Task created successfully! Link: {self.jira_client.create_issue.return_value.permalink()}",
            reply_markup=None,
        )

    async def test_add_attachment_with_files(self):
        # Simulate user uploading attachments and typing 'done'
        self.update.message.text = None
        self.update.message.media_group_id = None
        self.update.message.photo = [MagicMock()]
        self.update.message.video = None
        self.update.message.audio = None
        self.update.message.document = None
        self.update.message.reply_text = AsyncMock()
        self.update.message.photo[-1].get_file = AsyncMock(
            return_value=MagicMock(file_path="path/to/file"),
        )

        self.context.user_data["task_data"] = TaskData()
        self.context.user_data["task_data"].config = self.user_config_dict
        self.context.user_data["task_data"].attachments = {
            "images": [],
            "videos": [],
            "audio": [],
            "documents": [],
        }

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            # Provide valid image data
            with open(f'{DEFAULT_PATH}/tests/samples/test_image.png', "rb") as f:
                valid_image_data = f.read()
            mock_response.read = AsyncMock(return_value=valid_image_data)
            mock_get.return_value.__aenter__.return_value = mock_response

            with patch('PIL.Image.open', return_value=MagicMock()):
                await self.task_creation.add_attachment(self.update, self.context)

        self.assertEqual(
            len(self.context.user_data["task_data"].attachments["images"]),
            1,
        )
        self.update.message.reply_text.assert_called_with(
            "Attachment received. You can send more, or type 'done' to finish.",
        )

        # Simulate user typing 'done'
        self.update.message.text = "done"
        await self.task_creation.add_attachment(self.update, self.context)

        # Should proceed to finalize task
        self.jira_client.create_issue.assert_called()
        self.update.message.reply_text.assert_called_with(
            f"Task created successfully! Link: {self.jira_client.create_issue.return_value.permalink()}",
            reply_markup=None,
        )

    def test_build_issue_fields(self):
        # Test the build_issue_fields method
        task_data = TaskData()
        task_data.project_key = "PA"
        task_data.summary = "Test Summary"
        task_data.description = "Test Description"
        task_data.task_type = "Task"
        task_data.component = "Component X"
        task_data.story_points = 5.0
        task_data.sprint_id = 101
        task_data.epic_link = "EPIC-1"
        task_data.release = "Version 1.0"

        issue_fields = self.task_creation.build_issue_fields(task_data)

        expected_fields = {
            "project": {"key": "PA"},
            "summary": "Test Summary",
            "description": "Test Description",
            "issuetype": {"name": "Task"},
            "components": [{"name": "Component X"}],
            "customfield_10106": 5.0,
            "customfield_10104": 101,
            "customfield_10105": "EPIC-1",
            "fixVersions": [{"name": "Version 1.0"}],
        }

        self.assertEqual(issue_fields, expected_fields)

    async def test_send_message_with_message(self):
        # Test send_message when update.message exists
        await self.task_creation.send_message(self.update, "Test message")
        self.update.message.reply_text.assert_called_with(
            "Test message",
            reply_markup=None,
        )

    async def test_send_message_with_callback_query(self):
        # Test send_message when update.callback_query exists
        query = MagicMock()
        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        self.update.message = None
        self.update.callback_query = query

        await self.task_creation.send_message(self.update, "Test callback message")
        query.message.edit_text.assert_called_with(
            "Test callback message",
            reply_markup=None,
        )

    async def test_send_message_error(self):
        # Test send_message when neither message nor callback_query exists
        self.update.message = None
        self.update.callback_query = None

        with self.assertRaises(Exception) as context:
            await self.task_creation.send_message(self.update, "Should raise exception")

        self.assertIn(
            "other type of message in send message is not handled",
            str(context.exception),
        )

    async def test_handle_attachments(self):
        # Test the handle_attachments method
        issue = MagicMock()
        attachments = {
            "images": [BytesIO(b"fake image data")],
            "videos": [BytesIO(b"fake video data")],
            "audio": [BytesIO(b"fake audio data")],
            "documents": [BytesIO(b"fake document data")],
        }
        await self.task_creation.handle_attachments(issue, attachments)

        self.assertEqual(self.jira_client.add_attachment.call_count, 4)

    def test_get_file_extension(self):
        # Test the get_file_extension method
        self.assertEqual(self.task_creation.get_file_extension("images"), "jpg")
        self.assertEqual(self.task_creation.get_file_extension("videos"), "mp4")
        self.assertEqual(self.task_creation.get_file_extension("audio"), "mp3")
        self.assertEqual(self.task_creation.get_file_extension("documents"), "txt")
        self.assertEqual(self.task_creation.get_file_extension("unknown"), "bin")


if __name__ == "__main__":
    unittest.main()
