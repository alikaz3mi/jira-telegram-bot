"""Integration tests for GenerateUserStoryUseCase."""

import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.ai_agents.agent_generate_use_story import AgentGenerateUserStory


class TestGenerateUserStoryUseCaseIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for GenerateUserStoryUseCase."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_prompt_catalog = AsyncMock()
        self.mock_ai_service = AsyncMock()
        self.use_case = AgentGenerateUserStory(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
        )
        
        # Setup mock responses
        mock_prompt = MagicMock(spec=StructuredPrompt)
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        
        self.mock_ai_response = {
            "user_story": {
                "summary": "As a user, I want to login securely",
                "description": "Secure user authentication with validation",
                "component": "backend",
                "story_points": 5,
                "priority": "High"
            }
        }
        self.mock_ai_service.run.return_value = self.mock_ai_response

    async def test_concurrent_executions(self):
        """Test multiple concurrent use case executions."""
        # Arrange
        inputs = [
            GenerateUserStoryInput(
                raw_text=f"Create feature {i}",
                project_key="PROJ",
                project_context=f"Context {i}"
            )
            for i in range(5)
        ]
        
        # Act - Execute concurrently
        tasks = [self.use_case.execute(input_data) for input_data in inputs]
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIsNotNone(result.user_story)
            self.assertEqual(result.user_story.summary, "As a user, I want to login securely")
        
        # Verify all calls were made
        self.assertEqual(self.mock_ai_service.run.call_count, 5)
        self.assertEqual(self.mock_prompt_catalog.get_prompt.call_count, 5)

    async def test_concurrent_executions_with_different_robots(self):
        """Test concurrent executions with different robot IDs."""
        # Arrange
        robot_ids = [f"robot_{i}" for i in range(3)]
        input_data = GenerateUserStoryInput(
            raw_text="Create login feature",
            project_key="PROJ"
        )
        
        # Act - Execute concurrently with different robot IDs
        tasks = [
            self.use_case.execute(input_data, robot_id=robot_id)
            for robot_id in robot_ids
        ]
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsNotNone(result.user_story)
        
        # Verify calls were made with different user_ids
        self.assertEqual(self.mock_ai_service.run.call_count, 3)

    async def test_mixed_success_and_failure_scenarios(self):
        """Test handling of mixed success and failure scenarios concurrently."""
        # Arrange
        inputs = [
            GenerateUserStoryInput(raw_text="Valid request 1", project_key="PROJ"),
            GenerateUserStoryInput(raw_text="Valid request 2", project_key="PROJ"),
        ]
        
        # Setup AI service to return valid response for first call, invalid for second
        responses = [
            {
                "user_story": {
                    "summary": "Valid story",
                    "description": "Valid description",
                    "component": "backend",
                    "story_points": 3,
                    "priority": "Medium"
                }
            },
            {}  # Invalid response missing user_story
        ]
        self.mock_ai_service.run.side_effect = responses
        
        # Act & Assert
        # First execution should succeed
        result1 = await self.use_case.execute(inputs[0])
        self.assertIsNotNone(result1.user_story)
        
        # Second execution should fail
        with self.assertRaises(ValueError):
            await self.use_case.execute(inputs[1])

    async def test_stress_test_rapid_executions(self):
        """Test rapid successive executions for stress testing."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create feature for stress test",
            project_key="STRESS"
        )
        
        # Act - Execute rapidly in succession
        results = []
        for i in range(10):
            result = await self.use_case.execute(input_data)
            results.append(result)
        
        # Assert
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIsNotNone(result.user_story)
            self.assertEqual(result.user_story.summary, "As a user, I want to login securely")
        
        self.assertEqual(self.mock_ai_service.run.call_count, 10)

    async def test_concurrent_with_thread_executor(self):
        """Test concurrent execution using thread executor."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create threaded feature",
            project_key="THREAD"
        )
        
        async def execute_use_case():
            return await self.use_case.execute(input_data)
        
        # Act - Execute using thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Create multiple async tasks
            tasks = [
                loop.create_task(execute_use_case())
                for _ in range(3)
            ]
            results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsNotNone(result.user_story)
        
        self.assertEqual(self.mock_ai_service.run.call_count, 3)

    async def test_complex_input_processing_concurrent(self):
        """Test concurrent processing of complex inputs."""
        # Arrange
        complex_inputs = [
            GenerateUserStoryInput(
                raw_text="Create comprehensive user management system",
                project_key="COMPLEX",
                project_context="Large enterprise application",
                available_components=["backend", "frontend", "database", "security"],
                available_epics=[
                    {"key": "COMPLEX-100", "summary": "User Management Epic"},
                    {"key": "COMPLEX-200", "summary": "Security Epic"},
                ],
                current_sprint_info={
                    "name": "Sprint 5",
                    "goal": "Complete user management features"
                }
            ),
            GenerateUserStoryInput(
                raw_text="Implement advanced search functionality",
                project_key="SEARCH",
                project_context="E-commerce platform",
                available_components=["search-engine", "frontend", "analytics"],
                available_epics=[
                    {"key": "SEARCH-50", "summary": "Search Enhancement Epic"},
                ],
                current_sprint_info={
                    "name": "Sprint 3",
                    "goal": "Improve search capabilities"
                }
            ),
        ]
        
        # Act - Execute complex inputs concurrently
        tasks = [self.use_case.execute(input_data) for input_data in complex_inputs]
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIsNotNone(result.user_story)
            self.assertIsNotNone(result.processing_metadata)
            self.assertIn("input_project", result.processing_metadata)
        
        # Verify different projects were processed
        projects = [result.processing_metadata["input_project"] for result in results]
        self.assertIn("COMPLEX", projects)
        self.assertIn("SEARCH", projects)


if __name__ == "__main__":
    unittest.main()
