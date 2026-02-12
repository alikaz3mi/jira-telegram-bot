"""Integration tests for SynthPM documentation generation."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import Mock

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase


class TestSynthPMDocumentationIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration test cases for SynthPM documentation generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_repository = AsyncMock()
        self.mock_settings = Mock()
        self.mock_user_config = Mock()
        self.mock_notification_gateway = AsyncMock()
        self.mock_acceptance_criteria_use_case = AsyncMock()
        self.mock_test_scenarios_use_case = AsyncMock()

        self.synth_pm_use_case = SynthPMUseCase(
            repository=self.mock_repository,
            settings=self.mock_settings,
            user_config=self.mock_user_config,
            notification_gateway=self.mock_notification_gateway,
            generate_acceptance_criteria_use_case=self.mock_acceptance_criteria_use_case,
            generate_test_scenarios_use_case=self.mock_test_scenarios_use_case,
        )

    async def test_generate_feature_documentation_success(self):
        """Test successful generation of complete feature documentation."""
        # Arrange
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="پیاده‌سازی ورود کاربران",
            description="سیستم احراز هویت برای کاربران",
            epic="احراز هویت و امنیت",
            departments="Backend,Frontend",  # String format as per entity
            status="۶",  # در حال پیاده سازی
            jira_issue_key="PC-123",
        )

        project_info = {
            "description": "سامانه چندکاناله پارس‌چت",
            "keywords": ["AI-Chatbot", "NLP", "Omnichannel-Support"],
        }

        # Mock acceptance criteria response
        acceptance_result = Mock()
        acceptance_result.user_story = "به‌عنوان یک کاربر، می‌خواهم بتوانم وارد سیستم شوم تا بتوانم از امکانات آن استفاده کنم."
        acceptance_result.acceptance_criteria = [
            "کاربر باید بتواند با ایمیل و رمز عبور وارد شود",
            "سیستم باید پیام خطای مناسب نمایش دهد",
        ]
        acceptance_result.delivery_process = [
            "طراحی UI ورود",
            "پیاده‌سازی API احراز هویت",
        ]

        # Mock test scenarios response
        test_scenario_1 = Mock()
        test_scenario_1.test_number = "TC-01"
        test_scenario_1.description = "تست ورود موفق با اطلاعات صحیح"
        test_scenario_1.status = "⬜"
        test_scenario_1.responsible = "تستر"
        test_scenario_1.dict.return_value = {
            "test_number": "TC-01",
            "description": "تست ورود موفق با اطلاعات صحیح",
            "status": "⬜",
            "responsible": "تستر",
        }

        test_result = Mock()
        test_result.test_scenarios = [test_scenario_1]

        self.mock_acceptance_criteria_use_case.execute.return_value = acceptance_result
        self.mock_test_scenarios_use_case.execute.return_value = test_result

        # Act
        result = await self.synth_pm_use_case.generate_feature_documentation(
            feature,
            project_info,
        )

        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("documentation", result)
        self.assertIn("یوزر استوری (User Story)", result["documentation"])
        self.assertIn("معیارهای پذیرش (Acceptance Criteria)", result["documentation"])
        self.assertIn("روش تست (Test Scenarios)", result["documentation"])

        # Verify use case calls
        self.mock_acceptance_criteria_use_case.execute.assert_called_once()
        self.mock_test_scenarios_use_case.execute.assert_called_once()

        # Check that project context was passed correctly
        acceptance_call_args = self.mock_acceptance_criteria_use_case.execute.call_args[
            1
        ]
        input_data = acceptance_call_args["input_data"]
        self.assertEqual(input_data.task_title, feature.task_title)
        self.assertEqual(input_data.epic_name, feature.epic)
        self.assertIn("پارس‌چت", input_data.project_info)
        self.assertEqual(input_data.related_departments, ["Backend", "Frontend"])

    async def test_update_feature_with_documentation_success(self):
        """Test successful update of feature with generated documentation."""
        # Arrange
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="تست آپدیت مستندات",
            jira_issue_key="PC-456",
        )

        self.mock_settings.pm_project_key = "MYPROJECT"

        # Mock repository methods
        self.mock_repository.get_project_info.return_value = {
            "description": "test project",
        }
        self.mock_repository.update_jira_task_description.return_value = True
        self.mock_repository.update_developer_board_feature.return_value = True

        # Mock documentation generation
        doc_result = {
            "status": "success",
            "documentation": "# مستندات تولید شده",
            "user_story": "یوزر استوری تست",
            "acceptance_criteria": ["معیار 1", "معیار 2"],
            "test_scenarios": [
                {
                    "test_number": "TC-01",
                    "description": "تست اول",
                    "status": "⬜",
                    "responsible": "تستر",
                },
            ],
        }

        # Mock the generate_feature_documentation method
        self.synth_pm_use_case.generate_feature_documentation = AsyncMock(
            return_value=doc_result,
        )

        # Act
        result = await self.synth_pm_use_case.update_feature_with_documentation(feature)

        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("Documentation updated", result["message"])

        # Verify repository calls
        self.mock_repository.get_project_info.assert_called_once_with("MYPROJECT")
        self.mock_repository.update_jira_task_description.assert_called_once()
        self.mock_repository.update_developer_board_feature.assert_called_once()

    async def test_documentation_generation_error_handling(self):
        """Test error handling in documentation generation."""
        # Arrange
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="تست خطا",
        )

        project_info = {}

        # Mock acceptance criteria use case to raise error
        self.mock_acceptance_criteria_use_case.execute.side_effect = Exception(
            "AI service error",
        )

        # Act
        result = await self.synth_pm_use_case.generate_feature_documentation(
            feature,
            project_info,
        )

        # Assert
        self.assertEqual(result["status"], "error")
        self.assertIn("Error generating documentation", result["message"])


if __name__ == "__main__":
    unittest.main()
