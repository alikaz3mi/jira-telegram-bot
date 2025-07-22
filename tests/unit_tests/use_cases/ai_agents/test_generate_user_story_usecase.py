"""Unit tests for GenerateUserStoryUseCase."""

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryResult
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import UserStoryCandidate
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.ai_agents.agent_generate_use_story import AgentGenerateUserStory


class TestGenerateUserStoryUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for GenerateUserStoryUseCase."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_prompt_catalog = AsyncMock()
        self.mock_ai_service = AsyncMock()
        self.use_case = AgentGenerateUserStory(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
        )

    def test_initialization(self):
        """Test use case initialization."""
        # Assert
        self.assertEqual(self.use_case.prompt_name, PromptNames.GENERATE_USER_STORY)
        self.assertEqual(self.use_case.prompt_catalog, self.mock_prompt_catalog)
        self.assertEqual(self.use_case.ai_service, self.mock_ai_service)

    async def test_execute_minimal_input(self):
        """Test execute with minimal input data."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create login feature",
            project_key="PROJ"
        )
        
        mock_prompt = MagicMock(spec=StructuredPrompt)
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        
        ai_response = {
            "user_story": {
                "summary": "As a user, I want to login",
                "description": "User authentication feature with secure login",
                "component": "backend",
                "story_points": 5,
                "priority": "High"
            }
        }
        self.mock_ai_service.run.return_value = ai_response
        
        # Act
        result = await self.use_case.execute(input_data)
        
        # Assert
        self.assertIsInstance(result, GenerateUserStoryResult)
        self.assertEqual(result.user_story.summary, "As a user, I want to login")
        self.assertEqual(result.user_story.description, "User authentication feature with secure login")
        self.assertEqual(result.user_story.story_points, 5)
        self.assertEqual(result.user_story.priority, "High")
        self.assertEqual(result.user_story.components, ["backend"])
        self.assertEqual(result.confidence_score, 0.85)

    async def test_execute_full_input(self):
        """Test execute with full input data."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create secure login with 2FA",
            project_key="PROJ",
            project_context="E-commerce platform",
            available_components=["backend", "frontend"],
            available_epics=[{"key": "PROJ-100", "summary": "Authentication Epic"}],
            current_sprint_info={"name": "Sprint 1", "goal": "Security features"}
        )
        
        mock_prompt = MagicMock(spec=StructuredPrompt)
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        
        ai_response = {
            "user_story": {
                "summary": "As a user, I want secure 2FA login",
                "description": "Two-factor authentication for enhanced security",
                "component": "backend",
                "story_points": 8,
                "priority": "High"
            }
        }
        self.mock_ai_service.run.return_value = ai_response
        
        # Act
        result = await self.use_case.execute(input_data)
        
        # Assert
        self.assertIsInstance(result, GenerateUserStoryResult)
        self.assertEqual(result.user_story.summary, "As a user, I want secure 2FA login")
        self.assertEqual(result.user_story.story_points, 8)
        self.assertIn("PROJ", result.processing_metadata["input_project"])

    async def test_execute_missing_summary_raises_error(self):
        """Test execute raises error when AI result missing summary."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create feature",
            project_key="PROJ"
        )
        
        mock_prompt = MagicMock(spec=StructuredPrompt)
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        
        ai_response = {
            "user_story": {
                "description": "Some description"
                # Missing summary
            }
        }
        self.mock_ai_service.run.return_value = ai_response
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(input_data)
        
        self.assertIn("missing user story summary", str(context.exception))

    async def test_execute_missing_user_story_field_raises_error(self):
        """Test execute raises error when AI result missing user_story field."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create feature",
            project_key="PROJ"
        )
        
        mock_prompt = MagicMock(spec=StructuredPrompt)
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        
        ai_response = {}  # Missing user_story field
        self.mock_ai_service.run.return_value = ai_response
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            await self.use_case.execute(input_data)
        
        self.assertIn("missing 'user_story' field", str(context.exception))

    def test_prepare_prompt_inputs_minimal(self):
        """Test _prepare_prompt_inputs with minimal data."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create login",
            project_key="PROJ"
        )
        
        # Act
        result = self.use_case._prepare_prompt_inputs(input_data)
        
        # Assert
        self.assertEqual(result["product_area"], "Project PROJ")
        self.assertEqual(result["description"], "Create login")
        self.assertEqual(result["business_goal"], "Deliver value to users and stakeholders")
        self.assertIn("No specific components", result["dependencies"])
        self.assertEqual(result["epic_context"], "No active epics")

    def test_prepare_prompt_inputs_full(self):
        """Test _prepare_prompt_inputs with full data."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create secure login",
            project_key="PROJ",
            project_context="E-commerce platform",
            available_components=["backend", "frontend"],
            available_epics=[{"key": "PROJ-100", "summary": "Auth Epic"}],
            current_sprint_info={"name": "Sprint 1", "goal": "Security"}
        )
        
        # Act
        result = self.use_case._prepare_prompt_inputs(input_data)
        
        # Assert
        self.assertEqual(result["product_area"], "E-commerce platform")
        self.assertEqual(result["description"], "Create secure login")
        self.assertIn("backend, frontend", result["dependencies"])
        self.assertIn("PROJ-100: Auth Epic", result["epic_context"])

    def test_format_components_empty(self):
        """Test _format_components with empty list."""
        # Act
        result = self.use_case._format_components([])
        
        # Assert
        self.assertEqual(result, "No specific components defined")

    def test_format_components_multiple(self):
        """Test _format_components with multiple components."""
        # Act
        result = self.use_case._format_components(["backend", "frontend", "database"])
        
        # Assert
        self.assertEqual(result, "backend, frontend, database")

    def test_format_epics_empty(self):
        """Test _format_epics with empty list."""
        # Act
        result = self.use_case._format_epics([])
        
        # Assert
        self.assertEqual(result, "No active epics")

    def test_format_epics_multiple(self):
        """Test _format_epics with multiple epics."""
        # Arrange
        epics = [
            {"key": "PROJ-100", "summary": "Authentication Epic"},
            {"key": "PROJ-200", "summary": "User Management Epic"}
        ]
        
        # Act
        result = self.use_case._format_epics(epics)
        
        # Assert
        self.assertIn("PROJ-100: Authentication Epic", result)
        self.assertIn("PROJ-200: User Management Epic", result)
        self.assertTrue(result.startswith("Available Epics:"))

    def test_format_sprint_info_none(self):
        """Test _format_sprint_info with None."""
        # Act
        result = self.use_case._format_sprint_info(None)
        
        # Assert
        self.assertEqual(result, "No active sprint")

    def test_format_sprint_info_full(self):
        """Test _format_sprint_info with full data."""
        # Arrange
        sprint_info = {"name": "Sprint 1", "goal": "Implement auth features"}
        
        # Act
        result = self.use_case._format_sprint_info(sprint_info)
        
        # Assert
        self.assertEqual(result, "Sprint 1 (Goal: Implement auth features)")


if __name__ == "__main__":
    unittest.main()
