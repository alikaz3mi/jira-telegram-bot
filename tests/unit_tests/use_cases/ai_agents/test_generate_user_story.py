"""Unit tests for GenerateUserStoryUseCase."""

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryResult
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.ai_agents.generate_user_story import GenerateUserStoryUseCase


class TestGenerateUserStoryUseCase(unittest.TestCase):
    """Test cases for GenerateUserStoryUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_prompt_catalog = AsyncMock()
        self.mock_ai_service = AsyncMock()
        self.use_case = GenerateUserStoryUseCase(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
        )

    def test_init_sets_correct_prompt_name(self):
        """Test that initialization sets the correct prompt name."""
        # Assert
        self.assertEqual(self.use_case.prompt_name, PromptNames.GENERATE_USER_STORY)

    async def test_aexecute_with_minimal_input(self):
        """Test execute with minimal input data."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create login feature",
            project_key="PROJ"
        )
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["product_area", "description"],
        )
        
        mock_ai_response = {
            "user_story": {
                "summary": "As a user, I want to login",
                "description": "User authentication feature",
                "story_points": 5,
                "priority": "High",
                "component": "authentication"
            }
        }
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.return_value = mock_ai_response
        
        # Act
        result = await self.use_case.execute(input_data)
        
        # Assert
        self.assertIsInstance(result, GenerateUserStoryResult)
        self.assertEqual(result.user_story.summary, "As a user, I want to login")
        self.assertEqual(result.user_story.description, "User authentication feature")
        self.assertEqual(result.user_story.story_points, 5)
        self.assertEqual(result.user_story.priority, "High")
        self.assertEqual(result.user_story.components, ["authentication"])
        
        # Verify AI service was called with correct inputs
        self.mock_ai_service.run.assert_called_once()
        call_args = self.mock_ai_service.run.call_args
        inputs = call_args[0][1]
        self.assertIn("description", inputs)
        self.assertEqual(inputs["description"], "Create login feature")

    async def test_aexecute_with_full_input(self):
        """Test execute with complete input data."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Implement secure login with 2FA",
            project_key="PROJ",
            project_context="E-commerce platform",
            available_components=["backend", "frontend", "security"],
            available_epics=[
                {"key": "PROJ-100", "summary": "User Management Epic"}
            ],
            current_sprint_info={
                "name": "Sprint 1",
                "goal": "Implement authentication"
            }
        )
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["product_area", "description"],
        )
        
        mock_ai_response = {
            "user_story": {
                "summary": "As a user, I want secure 2FA login",
                "description": "Secure two-factor authentication",
                "story_points": 8,
                "priority": "Critical",
                "component": "security"
            }
        }
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.return_value = mock_ai_response
        
        # Act
        result = await self.use_case.execute(input_data, robot_id="user123")
        
        # Assert
        self.assertIsInstance(result, GenerateUserStoryResult)
        self.assertEqual(result.user_story.summary, "As a user, I want secure 2FA login")
        self.assertEqual(result.user_story.story_points, 8)
        self.assertEqual(result.user_story.priority, "Critical")
        
        # Verify prompt inputs include context
        call_args = self.mock_ai_service.run.call_args
        inputs = call_args[0][1]
        self.assertEqual(inputs["product_area"], "E-commerce platform")
        self.assertIn("backend, frontend, security", inputs["dependencies"])
        self.assertIn("PROJ-100: User Management Epic", inputs["epic_context"])

    async def test_aexecute_raises_error_on_empty_ai_response(self):
        """Test that execute raises error when AI returns empty response."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create feature",
            project_key="PROJ"
        )
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["description"],
        )
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.return_value = {}  # Empty response
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(input_data)
        
        self.assertIn("empty user story data", str(context.exception))

    def test_format_components_with_empty_list(self):
        """Test formatting components with empty list."""
        # Act
        result = self.use_case._format_components([])
        
        # Assert
        self.assertEqual(result, "No specific components defined")

    def test_format_components_with_multiple_items(self):
        """Test formatting components with multiple items."""
        # Arrange
        components = ["backend", "frontend", "database"]
        
        # Act
        result = self.use_case._format_components(components)
        
        # Assert
        self.assertEqual(result, "backend, frontend, database")

    def test_format_epics_with_empty_list(self):
        """Test formatting epics with empty list."""
        # Act
        result = self.use_case._format_epics([])
        
        # Assert
        self.assertEqual(result, "No active epics")

    def test_format_epics_with_multiple_items(self):
        """Test formatting epics with multiple items."""
        # Arrange
        epics = [
            {"key": "PROJ-100", "summary": "Epic 1"},
            {"key": "PROJ-200", "summary": "Epic 2"}
        ]
        
        # Act
        result = self.use_case._format_epics(epics)
        
        # Assert
        expected = "Available Epics:\n- PROJ-100: Epic 1\n- PROJ-200: Epic 2"
        self.assertEqual(result, expected)

    def test_format_sprint_info_with_none(self):
        """Test formatting sprint info with None."""
        # Act
        result = self.use_case._format_sprint_info(None)
        
        # Assert
        self.assertEqual(result, "No active sprint")

    def test_format_sprint_info_with_data(self):
        """Test formatting sprint info with complete data."""
        # Arrange
        sprint_info = {
            "name": "Sprint 5",
            "goal": "Complete user authentication"
        }
        
        # Act
        result = self.use_case._format_sprint_info(sprint_info)
        
        # Assert
        expected = "Sprint 5 (Goal: Complete user authentication)"
        self.assertEqual(result, expected)

    def test_format_sprint_info_with_missing_fields(self):
        """Test formatting sprint info with missing fields."""
        # Arrange
        sprint_info = {"name": "Sprint 3"}  # Missing goal
        
        # Act
        result = self.use_case._format_sprint_info(sprint_info)
        
        # Assert
        expected = "Sprint 3 (Goal: No goal defined)"
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
