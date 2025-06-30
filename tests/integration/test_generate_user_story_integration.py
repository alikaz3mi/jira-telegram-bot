"""Integration tests for GenerateUserStoryUseCase."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.ai_agents.generate_user_story import GenerateUserStoryUseCase


class TestGenerateUserStoryUseCaseIntegration(unittest.TestCase):
    """Integration tests for GenerateUserStoryUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_prompt_catalog = AsyncMock()
        self.mock_ai_service = AsyncMock()
        self.use_case = GenerateUserStoryUseCase(
            prompt_catalog=self.mock_prompt_catalog,
            ai_service=self.mock_ai_service,
        )

    async def test_aconcurrent_execution(self):
        """Test concurrent execution of multiple user story generations."""
        # Arrange
        input_data_list = [
            GenerateUserStoryInput(
                raw_text=f"Create feature {i}",
                project_key="PROJ"
            ) for i in range(5)
        ]
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["description"],
        )
        
        def mock_ai_response(prompt, inputs):
            feature_num = inputs["description"].split()[-1]
            return {
                "user_story": {
                    "summary": f"As a user, I want feature {feature_num}",
                    "description": f"Feature {feature_num} description",
                    "story_points": 3,
                    "priority": "Medium",
                    "component": "backend"
                }
            }
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.side_effect = mock_ai_response
        
        # Act - Execute concurrently
        tasks = [
            self.use_case.execute(input_data)
            for input_data in input_data_list
        ]
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 5)
        for i, result in enumerate(results):
            self.assertIn(f"feature {i}", result.user_story.summary)
            self.assertEqual(result.user_story.story_points, 3)
        
        # Verify all AI service calls were made
        self.assertEqual(self.mock_ai_service.run.call_count, 5)

    async def test_aerror_handling_in_concurrent_execution(self):
        """Test error handling during concurrent execution."""
        # Arrange
        input_data_list = [
            GenerateUserStoryInput(
                raw_text=f"Create feature {i}",
                project_key="PROJ"
            ) for i in range(3)
        ]
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["description"],
        )
        
        def mock_ai_response_with_error(prompt, inputs):
            if "feature 1" in inputs["description"]:
                return {}  # Empty response to trigger error
            return {
                "user_story": {
                    "summary": "As a user, I want a feature",
                    "description": "Feature description",
                    "story_points": 3,
                    "priority": "Medium",
                    "component": "backend"
                }
            }
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.side_effect = mock_ai_response_with_error
        
        # Act & Assert - Execute concurrently with error handling
        tasks = [
            self.use_case.execute(input_data)
            for input_data in input_data_list
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert
        self.assertEqual(len(results), 3)
        # First result should be successful
        self.assertIsNotNone(results[0].user_story.summary)
        # Second result should be an exception
        self.assertIsInstance(results[1], ValueError)
        # Third result should be successful
        self.assertIsNotNone(results[2].user_story.summary)

    async def test_amemory_usage_with_large_inputs(self):
        """Test memory usage with large input data."""
        # Arrange
        large_text = "Create a comprehensive feature that handles " + "x" * 10000
        large_components = [f"component_{i}" for i in range(100)]
        large_epics = [
            {"key": f"PROJ-{i}", "summary": f"Epic {i} with long description " + "y" * 100}
            for i in range(50)
        ]
        
        input_data = GenerateUserStoryInput(
            raw_text=large_text,
            project_key="PROJ",
            available_components=large_components,
            available_epics=large_epics,
        )
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["description"],
        )
        
        mock_ai_response = {
            "user_story": {
                "summary": "As a user, I want a complex feature",
                "description": "Complex feature description",
                "story_points": 13,
                "priority": "High",
                "component": "backend"
            }
        }
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.return_value = mock_ai_response
        
        # Act
        result = await self.use_case.execute(input_data)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.user_story.story_points, 13)
        self.assertEqual(result.user_story.priority, "High")
        
        # Verify that large inputs were processed correctly
        call_args = self.mock_ai_service.run.call_args
        inputs = call_args[0][1]
        self.assertIn("component_0, component_1", inputs["dependencies"])
        self.assertIn("PROJ-0: Epic 0", inputs["epic_context"])

    async def test_atimeout_handling(self):
        """Test timeout handling for long-running operations."""
        # Arrange
        input_data = GenerateUserStoryInput(
            raw_text="Create timeout test feature",
            project_key="PROJ"
        )
        
        mock_prompt = StructuredPrompt(
            template="test template",
            schemas=[],
            input_variables=["description"],
        )
        
        async def slow_ai_response(prompt, inputs):
            await asyncio.sleep(0.1)  # Simulate slow response
            return {
                "user_story": {
                    "summary": "As a user, I want a slow feature",
                    "description": "Slow feature description",
                    "story_points": 5,
                    "priority": "Low",
                    "component": "backend"
                }
            }
        
        self.mock_prompt_catalog.get_prompt.return_value = mock_prompt
        self.mock_ai_service.run.side_effect = slow_ai_response
        
        # Act
        result = await asyncio.wait_for(
            self.use_case.execute(input_data),
            timeout=1.0  # 1 second timeout
        )
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.user_story.summary, "As a user, I want a slow feature")


def run_integration_tests():
    """Run integration tests asynchronously."""
    async def run_all_tests():
        suite = unittest.TestLoader().loadTestsFromTestCase(TestGenerateUserStoryUseCaseIntegration)
        test_cases = [test for test in suite]
        
        for test_case in test_cases:
            test_method_name = test_case._testMethodName
            if test_method_name.startswith('test_a'):  # Async tests
                test_method = getattr(test_case, test_method_name)
                try:
                    test_case.setUp()
                    await test_method()
                    print(f"✓ {test_method_name} passed")
                except Exception as e:
                    print(f"✗ {test_method_name} failed: {e}")
    
    asyncio.run(run_all_tests())


if __name__ == "__main__":
    run_integration_tests()
