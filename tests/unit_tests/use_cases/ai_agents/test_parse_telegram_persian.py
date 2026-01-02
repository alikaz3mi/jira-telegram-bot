"""Unit tests for Persian Telegram message parsing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue import (
    parse_jira_prompt,
)


class TestPersianMessageParsing(unittest.TestCase):
    """Test parsing of Persian Telegram messages with hashtags and mixed content."""

    def setUp(self):
        """Set up test fixtures."""
        self.persian_message_with_hashtags = """سلام وقت بخیر 
دوستان عزیز با هماهنگی با آقای نسیم و تیم فنی، از این پس تمام راه اندازی های اختصاصی در این کانال ارسال می شود و نتیجه به صورت کامل و با جزئیات اعلام و اتمام کار هم با تاریخ اعلام می شود.
 مواردی که نیاز به برآورد نفر ساعت نیروی فنی هست با #برآورد_قیمت
و مواردی که پس از برآورد فنی و تشخیصات مالی برای اقدام در نظر گرفته میشوند با #راه_اندازی_اختصاصی مشخص میشود.
"""

        self.mixed_content_message = """Bug Report: Login Issue
مشکل در ورود به سیستم
- User cannot login
- خطای 500 رخ می‌دهد
#BUG #URGENT #ورود"""

        self.english_only_message = """Implement new feature for user profile page
- Add avatar upload
- Add bio section
- Update settings page
#FEATURE #UI"""

    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.ChatOpenAI")
    @patch(
        "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue._load_prompt_config"
    )
    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.OpenAISettings")
    def test_parse_persian_message_with_hashtags(
        self, mock_settings, mock_load_config, mock_openai
    ):
        """Test parsing Persian message extracts hashtags and summary correctly."""
        # Setup mock configuration
        mock_config = {
            "model_hint": "gpt-4o-mini",
            "temperature": 0.2,
            "prompt": "Test prompt {content}",
            "input_variables": ["content"],
            "schemas": [
                {"name": "summary", "description": "Task summary"},
                {"name": "task_type", "description": "Task type"},
                {"name": "description", "description": "Full description"},
                {"name": "labels", "description": "Hashtag labels"},
            ],
        }
        mock_load_config.return_value = mock_config

        # Setup mock AI response
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "summary": "راه‌اندازی‌های اختصاصی و برآورد قیمت",
            "task_type": "Task",
            "description": self.persian_message_with_hashtags,
            "labels": "#برآورد_قیمت, #راه_اندازی_اختصاصی",
        }

        mock_llm_instance = MagicMock()
        mock_openai.return_value = mock_llm_instance

        with patch(
            "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.PromptTemplate"
        ) as mock_prompt_template:
            mock_prompt_instance = MagicMock()
            mock_prompt_template.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )

            result = parse_jira_prompt(self.persian_message_with_hashtags)

        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("summary", result)
        self.assertIn("task_type", result)
        self.assertIn("description", result)
        self.assertIn("labels", result)

        # Verify summary is present
        self.assertTrue(len(result["summary"]) > 0)

        # Verify task type is valid
        self.assertIn(result["task_type"], ["Task", "Bug"])

        # Verify labels are extracted as list
        self.assertIsInstance(result["labels"], list)
        self.assertTrue(len(result["labels"]) > 0)

        # Verify Persian hashtags are preserved
        labels_str = ",".join(result["labels"])
        self.assertIn("برآورد_قیمت", labels_str)
        self.assertIn("راه_اندازی_اختصاصی", labels_str)

    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.ChatOpenAI")
    @patch(
        "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue._load_prompt_config"
    )
    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.OpenAISettings")
    def test_parse_mixed_persian_english_message(
        self, mock_settings, mock_load_config, mock_openai
    ):
        """Test parsing message with mixed Persian and English content."""
        mock_config = {
            "model_hint": "gpt-4o-mini",
            "temperature": 0.2,
            "prompt": "Test prompt {content}",
            "input_variables": ["content"],
            "schemas": [
                {"name": "summary", "description": "Task summary"},
                {"name": "task_type", "description": "Task type"},
                {"name": "description", "description": "Full description"},
                {"name": "labels", "description": "Hashtag labels"},
            ],
        }
        mock_load_config.return_value = mock_config

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "summary": "Login Issue - مشکل ورود",
            "task_type": "Bug",
            "description": self.mixed_content_message,
            "labels": "#BUG, #URGENT, #ورود",
        }

        mock_llm_instance = MagicMock()
        mock_openai.return_value = mock_llm_instance

        with patch(
            "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.PromptTemplate"
        ) as mock_prompt_template:
            mock_prompt_instance = MagicMock()
            mock_prompt_template.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )

            result = parse_jira_prompt(self.mixed_content_message)

        # Assertions
        self.assertEqual(result["task_type"], "Bug")
        self.assertIsInstance(result["labels"], list)
        self.assertTrue(any("BUG" in label for label in result["labels"]))
        self.assertTrue(any("ورود" in label for label in result["labels"]))

    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.ChatOpenAI")
    @patch(
        "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue._load_prompt_config"
    )
    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.OpenAISettings")
    def test_parse_english_message_with_hashtags(
        self, mock_settings, mock_load_config, mock_openai
    ):
        """Test parsing English-only message with hashtags."""
        mock_config = {
            "model_hint": "gpt-4o-mini",
            "temperature": 0.2,
            "prompt": "Test prompt {content}",
            "input_variables": ["content"],
            "schemas": [
                {"name": "summary", "description": "Task summary"},
                {"name": "task_type", "description": "Task type"},
                {"name": "description", "description": "Full description"},
                {"name": "labels", "description": "Hashtag labels"},
            ],
        }
        mock_load_config.return_value = mock_config

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "summary": "Implement user profile page features",
            "task_type": "Task",
            "description": self.english_only_message,
            "labels": "#FEATURE, #UI",
        }

        mock_llm_instance = MagicMock()
        mock_openai.return_value = mock_llm_instance

        with patch(
            "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.PromptTemplate"
        ) as mock_prompt_template:
            mock_prompt_instance = MagicMock()
            mock_prompt_template.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )

            result = parse_jira_prompt(self.english_only_message)

        # Assertions
        self.assertEqual(result["task_type"], "Task")
        self.assertIsInstance(result["labels"], list)
        self.assertTrue(any("FEATURE" in label for label in result["labels"]))
        self.assertTrue(any("UI" in label for label in result["labels"]))

    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.ChatOpenAI")
    @patch(
        "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue._load_prompt_config"
    )
    def test_parse_message_handles_ai_failure_gracefully(
        self, mock_load_config, mock_openai
    ):
        """Test that parsing returns fallback values when AI fails."""
        mock_load_config.side_effect = Exception("AI service unavailable")

        result = parse_jira_prompt(self.persian_message_with_hashtags)

        # Verify fallback behavior
        self.assertIsNotNone(result)
        self.assertIn("summary", result)
        self.assertIn("task_type", result)
        self.assertIn("description", result)
        self.assertIn("labels", result)

        # Verify fallback values
        self.assertEqual(result["task_type"], "Task")
        self.assertEqual(result["description"], "")
        self.assertIsInstance(result["labels"], list)

        # Summary should be truncated message
        self.assertTrue(len(result["summary"]) <= 80)

    def test_parse_empty_message(self):
        """Test parsing empty message."""
        result = parse_jira_prompt("")

        # Should return fallback values
        self.assertEqual(result["summary"], "No Summary")
        self.assertEqual(result["task_type"], "Task")
        self.assertEqual(result["description"], "")
        self.assertEqual(result["labels"], [])

    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.ChatOpenAI")
    @patch(
        "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue._load_prompt_config"
    )
    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.OpenAISettings")
    def test_labels_split_correctly(self, mock_settings, mock_load_config, mock_openai):
        """Test that labels are correctly split from comma-separated string."""
        mock_config = {
            "model_hint": "gpt-4o-mini",
            "temperature": 0.2,
            "prompt": "Test prompt {content}",
            "input_variables": ["content"],
            "schemas": [
                {"name": "summary", "description": "Task summary"},
                {"name": "task_type", "description": "Task type"},
                {"name": "description", "description": "Full description"},
                {"name": "labels", "description": "Hashtag labels"},
            ],
        }
        mock_load_config.return_value = mock_config

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "summary": "Test",
            "task_type": "Task",
            "description": "Test description",
            "labels": "#TAG1, #TAG2  ,  #TAG3,#TAG4",  # Various spacing
        }

        mock_llm_instance = MagicMock()
        mock_openai.return_value = mock_llm_instance

        with patch(
            "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.PromptTemplate"
        ) as mock_prompt_template:
            mock_prompt_instance = MagicMock()
            mock_prompt_template.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )

            result = parse_jira_prompt("Test message")

        # Verify labels are properly split and trimmed
        self.assertEqual(len(result["labels"]), 4)
        self.assertIn("#TAG1", result["labels"])
        self.assertIn("#TAG2", result["labels"])
        self.assertIn("#TAG3", result["labels"])
        self.assertIn("#TAG4", result["labels"])

    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.ChatOpenAI")
    @patch(
        "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue._load_prompt_config"
    )
    @patch("jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.OpenAISettings")
    def test_empty_labels_returns_empty_list(
        self, mock_settings, mock_load_config, mock_openai
    ):
        """Test that empty labels string returns empty list."""
        mock_config = {
            "model_hint": "gpt-4o-mini",
            "temperature": 0.2,
            "prompt": "Test prompt {content}",
            "input_variables": ["content"],
            "schemas": [
                {"name": "summary", "description": "Task summary"},
                {"name": "task_type", "description": "Task type"},
                {"name": "description", "description": "Full description"},
                {"name": "labels", "description": "Hashtag labels"},
            ],
        }
        mock_load_config.return_value = mock_config

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "summary": "Test",
            "task_type": "Task",
            "description": "Test description",
            "labels": "",
        }

        mock_llm_instance = MagicMock()
        mock_openai.return_value = mock_llm_instance

        with patch(
            "jira_telegram_bot.use_cases.ai_agents.create_ticketing_issue.PromptTemplate"
        ) as mock_prompt_template:
            mock_prompt_instance = MagicMock()
            mock_prompt_template.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )

            result = parse_jira_prompt("Test message")

        # Verify empty labels returns empty list
        self.assertEqual(result["labels"], [])


if __name__ == "__main__":
    unittest.main()
