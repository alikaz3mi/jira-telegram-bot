"""Unit tests for generate test scenarios use case."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import (
    GenerateTestScenariosInput,
)
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import (
    GenerateTestScenariosResult,
)
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import SynthPMTestScenario
from jira_telegram_bot.use_cases.ai_agents.generate_test_scenarios import (
    GenerateTestScenariosUseCase,
)


class TestGenerateTestScenariosUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for GenerateTestScenariosUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_prompt_catalog = AsyncMock()
        self.mock_ai_service = AsyncMock()
        
        self.use_case = GenerateTestScenariosUseCase(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
        )

    async def test_execute_success(self):
        """Test successful execution of test scenarios generation."""
        # Arrange
        input_data = GenerateTestScenariosInput(
            task_title="تست ورود کاربران",
            task_description="پیاده‌سازی سیستم ورود کاربران",
            user_story="به‌عنوان یک کاربر، می‌خواهم بتوانم وارد سیستم شوم",
            acceptance_criteria=["کاربر باید بتواند با ایمیل وارد شود"],
            epic_name="احراز هویت",
            related_departments=["Backend", "Frontend"],
        )

        mock_ai_response = {
            "result": {
                "test_scenarios": [
                    {
                        "test_number": "TC-01",
                        "description": "تست ورود موفق با ایمیل و رمز عبور صحیح",
                        "status": "⬜",
                        "responsible": "تستر",
                    },
                    {
                        "test_number": "TC-02",
                        "description": "تست ورود ناموفق با رمز عبور اشتباه",
                        "status": "⬜",
                        "responsible": "توسعه‌دهنده",
                    },
                ]
            }
        }

        self.mock_ai_service.run.return_value = mock_ai_response

        # Act
        result = await self.use_case.execute(input_data)

        # Assert
        self.assertIsInstance(result, GenerateTestScenariosResult)
        self.assertEqual(len(result.test_scenarios), 2)
        
        first_scenario = result.test_scenarios[0]
        self.assertIsInstance(first_scenario, SynthPMTestScenario)
        self.assertEqual(first_scenario.test_number, "TC-01")
        self.assertEqual(first_scenario.status, "⬜")
        self.assertEqual(first_scenario.responsible, "تستر")
        
        self.assertEqual(result.metadata["task_title"], input_data.task_title)
        self.assertEqual(result.metadata["total_scenarios"], 2)

    async def test_execute_empty_response(self):
        """Test handling of empty AI response."""
        # Arrange
        input_data = GenerateTestScenariosInput(
            task_title="تست خالی",
        )

        mock_ai_response = {
            "result": {
                "test_scenarios": []
            }
        }

        self.mock_ai_service.run.return_value = mock_ai_response

        # Act
        result = await self.use_case.execute(input_data)

        # Assert
        self.assertIsInstance(result, GenerateTestScenariosResult)
        self.assertEqual(len(result.test_scenarios), 0)
        self.assertEqual(result.metadata["total_scenarios"], 0)

    async def test_execute_ai_service_error(self):
        """Test handling of AI service errors."""
        # Arrange
        input_data = GenerateTestScenariosInput(
            task_title="تست خطا",
        )

        self.mock_ai_service.run.side_effect = Exception("AI service error")

        # Act & Assert
        with self.assertRaises(Exception) as context:
            await self.use_case.execute(input_data)

        self.assertIn("Failed to generate test scenarios", str(context.exception))


if __name__ == "__main__":
    unittest.main()
