"""Test cases for GenerateUserStoryUseCase."""

import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryResult
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import UserStoryCandidate
from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.entities.user_story_generation_request import UserStoryGenerationRequest
from jira_telegram_bot.use_cases.generate_user_story import GenerateUserStoryUseCase


class TestGenerateUserStoryUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for GenerateUserStoryUseCase."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_ai_generate_user_story = AsyncMock()
        self.use_case = GenerateUserStoryUseCase(
            ai_generate_user_story=self.mock_ai_generate_user_story
        )

    async def test_a_execute_with_valid_input(self):
        """Test successful execution with valid input."""
        # Arrange
        request = UserStoryGenerationRequest(
            raw_text="I need a login feature for users to authenticate",
            project="PROJ"
        )
        
        mock_ai_result = GenerateUserStoryResult(
            user_story=UserStoryCandidate(
                summary="As a user, I want to log in so that I can access my account",
                description="User authentication feature allowing secure login",
                components=["backend", "frontend"],
                story_points=5,
                priority="High"
            )
        )
        
        expected_user_story = UserStory(
            project_key=request.project,
            summary="As a user, I want to log in so that I can access my account",
            description="User authentication feature allowing secure login",
            components=["backend", "frontend"],
            story_points=5.0,
            priority="High",
            task_type="Story"
        )
        
        self.mock_ai_generate_user_story.execute.return_value = mock_ai_result
        
        # Act
        result = await self.use_case(request)
        
        # Assert
        self.assertEqual(result.project_key, expected_user_story.project_key)
        self.assertEqual(result.summary, expected_user_story.summary)
        self.assertEqual(result.description, expected_user_story.description)
        self.assertEqual(result.components, expected_user_story.components)
        self.assertEqual(result.story_points, expected_user_story.story_points)
        self.assertEqual(result.priority, expected_user_story.priority)
        self.assertEqual(result.task_type, expected_user_story.task_type)
        
        # Verify the AI use case was called correctly
        self.mock_ai_generate_user_story.execute.assert_called_once()
        call_args = self.mock_ai_generate_user_story.execute.call_args[0][0]
        self.assertEqual(call_args.raw_text, request.raw_text)
        self.assertEqual(call_args.project_key, request.project)

    async def test_a_execute_with_additional_context(self):
        """Test execution with additional context parameters."""
        # Arrange
        request = UserStoryGenerationRequest(
            raw_text="Add payment processing for subscriptions",
            project="PROJ",
            product_area="E-commerce",
            business_goal="Increase revenue"
        )
        
        mock_ai_result = GenerateUserStoryResult(
            user_story=UserStoryCandidate(
                summary="As a user, I want to pay for subscriptions so that I can access premium features",
                description="Payment processing for subscription services",
                components=["payment", "backend"],
                story_points=8,
                priority="High"
            )
        )
        
        expected_user_story = UserStory(
            project_key=request.project,
            summary="As a user, I want to pay for subscriptions so that I can access premium features",
            description="Payment processing for subscription services",
            components=["payment", "backend"],
            story_points=8.0,
            priority="High",
            task_type="Story"
        )
        
        self.mock_ai_generate_user_story.execute.return_value = mock_ai_result
        
        # Act
        result = await self.use_case(request)
        
        # Assert
        self.assertEqual(result.project_key, expected_user_story.project_key)
        self.assertEqual(result.summary, expected_user_story.summary)
        self.assertEqual(result.description, expected_user_story.description)
        self.assertEqual(result.components, expected_user_story.components)
        self.assertEqual(result.story_points, expected_user_story.story_points)
        self.assertEqual(result.priority, expected_user_story.priority)
        
        # Verify the AI use case was called correctly
        self.mock_ai_generate_user_story.execute.assert_called_once()
        call_args = self.mock_ai_generate_user_story.execute.call_args[0][0]
        self.assertEqual(call_args.raw_text, request.raw_text)
        self.assertEqual(call_args.project_key, request.project)
        self.assertEqual(call_args.project_context, request.product_area)

    async def test_a_execute_with_empty_raw_text(self):
        """Test execution with empty raw text."""
        # Arrange
        request = UserStoryGenerationRequest(
            raw_text="",
            project="PROJ"
        )
        
        mock_ai_result = GenerateUserStoryResult(
            user_story=UserStoryCandidate(
                summary="Default story",
                description="Default description",
                story_points=1,
                priority="Low"
            )
        )
        
        expected_user_story = UserStory(
            project_key=request.project,
            summary="Default story",
            description="Default description",
            story_points=1.0,
            priority="Low",
            task_type="Story"
        )
        
        self.mock_ai_generate_user_story.execute.return_value = mock_ai_result
        
        # Act
        result = await self.use_case(request)
        
        # Assert
        self.assertEqual(result.project_key, expected_user_story.project_key)
        self.assertEqual(result.summary, expected_user_story.summary)
        self.assertEqual(result.description, expected_user_story.description)
        self.assertEqual(result.story_points, expected_user_story.story_points)
        self.assertEqual(result.priority, expected_user_story.priority)
        self.assertEqual(result.task_type, expected_user_story.task_type)
        
        # Verify the AI use case was called correctly
        self.mock_ai_generate_user_story.execute.assert_called_once()
        call_args = self.mock_ai_generate_user_story.execute.call_args[0][0]
        self.assertEqual(call_args.raw_text, request.raw_text)
        self.assertEqual(call_args.project_key, request.project)

    async def test_a_execute_handles_generator_exception(self):
        """Test that exceptions from AI use case are propagated."""
        # Arrange
        request = UserStoryGenerationRequest(
            raw_text="Invalid input",
            project="PROJ"
        )
        
        self.mock_ai_generate_user_story.execute.side_effect = Exception("AI service error")
        
        # Act & Assert
        with self.assertRaises(Exception) as context:
            await self.use_case(request)
        
        self.assertEqual(str(context.exception), "AI service error")
        
        # Verify the AI use case was called correctly
        self.mock_ai_generate_user_story.execute.assert_called_once()
        call_args = self.mock_ai_generate_user_story.execute.call_args[0][0]
        self.assertEqual(call_args.raw_text, request.raw_text)
        self.assertEqual(call_args.project_key, request.project)


if __name__ == "__main__":
    unittest.main()
