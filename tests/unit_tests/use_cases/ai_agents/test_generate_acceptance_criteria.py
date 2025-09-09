"""Unit tests for generate acceptance criteria use case."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.ai_agent_models.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaInput,
)
from jira_telegram_bot.entities.ai_agent_models.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaResult,
)
from jira_telegram_bot.use_cases.ai_agents.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaUseCase,
)


class TestGenerateAcceptanceCriteriaUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for GenerateAcceptanceCriteriaUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_prompt_catalog = AsyncMock()
        self.mock_ai_service = AsyncMock()
        
        self.use_case = GenerateAcceptanceCriteriaUseCase(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
        )

    async def test_execute_success(self):
        """Test successful execution of acceptance criteria generation."""
        # Arrange
        input_data = GenerateAcceptanceCriteriaInput(
            task_title="تست ورود کاربران",
            task_description="پیاده‌سازی سیستم ورود کاربران",
            epic_name="احراز هویت",
            related_departments=["Backend", "Frontend"],
            project_info="پروژه پارس‌چت",
        )

        mock_ai_response = {
            "result": {
                "user_story": "به‌عنوان یک کاربر، می‌خواهم بتوانم وارد سیستم شوم تا بتوانم از امکانات آن استفاده کنم.",
                "acceptance_criteria": [
                    "کاربر باید بتواند با ایمیل و رمز عبور وارد شود",
                    "سیستم باید پیام خطای مناسب نمایش دهد",
                ],
                "delivery_process": [
                    "طراحی UI ورود",
                    "پیاده‌سازی API احراز هویت",
                    "تست و بررسی امنیت",
                ],
            }
        }

        self.mock_ai_service.run.return_value = mock_ai_response

        # Act
        result = await self.use_case.execute(input_data)

        # Assert
        self.assertIsInstance(result, GenerateAcceptanceCriteriaResult)
        self.assertEqual(result.user_story, mock_ai_response["result"]["user_story"])
        self.assertEqual(result.acceptance_criteria, mock_ai_response["result"]["acceptance_criteria"])
        self.assertEqual(result.delivery_process, mock_ai_response["result"]["delivery_process"])
        self.assertEqual(result.metadata["task_title"], input_data.task_title)

    async def test_execute_ai_service_error(self):
        """Test handling of AI service errors."""
        # Arrange
        input_data = GenerateAcceptanceCriteriaInput(
            task_title="تست خطا",
        )

        self.mock_ai_service.run.side_effect = Exception("AI service error")

        # Act & Assert
        with self.assertRaises(Exception) as context:
            await self.use_case.execute(input_data)

        self.assertIn("Failed to generate acceptance criteria", str(context.exception))


if __name__ == "__main__":
    unittest.main()
