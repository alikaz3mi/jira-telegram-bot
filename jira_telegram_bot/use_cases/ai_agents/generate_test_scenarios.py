"""Generate test scenarios AI agent use case."""

from __future__ import annotations

from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import (
    GenerateTestScenariosInput,
)
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import (
    GenerateTestScenariosResult,
)
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import SynthPMTestScenario
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase


class GenerateTestScenariosUseCase(BaseAIAgentUseCase):
    """AI agent use case for generating test scenarios."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the generate test scenarios use case.

        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.GENERATE_TEST_SCENARIOS

    async def execute(
        self,
        input_data: GenerateTestScenariosInput,
        robot_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> GenerateTestScenariosResult:
        """Execute test scenarios generation from input data.

        Args:
            input_data: Input data containing task details and context.
            robot_id: Optional robot/user ID for prompt customization.
            prompt_version: Optional prompt version (unused for now).

        Returns:
            Generated test scenarios result with structured test cases.

        Raises:
            Exception: If AI service processing fails.
        """
        try:
            LOGGER.info(f"Generating test scenarios for task: {input_data.task_title}")

            # Prepare input variables for the prompt
            prompt_inputs = {
                "task_title": input_data.task_title,
                "task_description": input_data.task_description or "",
                "user_story": input_data.user_story or "",
                "acceptance_criteria": "\n".join(input_data.acceptance_criteria) 
                    if input_data.acceptance_criteria else "",
                "epic_name": input_data.epic_name or "مشخص نشده",
                "related_departments": ", ".join(input_data.related_departments) 
                    if input_data.related_departments else "مشخص نشده",
                "project_info": input_data.project_info or "",
            }

            # Process with AI service
            ai_response = await self._process_with_ai(
                inputs=prompt_inputs,
                department=None,
                user_id=robot_id,
            )

            # Parse AI response
            result_data = ai_response.get("result", {})
            test_scenarios_data = result_data.get("test_scenarios", [])
            
            # Convert to TestScenario objects
            test_scenarios = []
            for scenario_data in test_scenarios_data:
                test_scenario = SynthPMTestScenario(
                    test_number=scenario_data.get("test_number", ""),
                    description=scenario_data.get("description", ""),
                    status=scenario_data.get("status", "⬜"),
                    responsible=scenario_data.get("responsible", "تستر"),
                )
                test_scenarios.append(test_scenario)

            result = GenerateTestScenariosResult(
                test_scenarios=test_scenarios,
                metadata={
                    "task_title": input_data.task_title,
                    "epic_name": input_data.epic_name,
                    "departments": input_data.related_departments,
                    "total_scenarios": len(test_scenarios),
                    "ai_model": "4o-mini",
                    "prompt_version": prompt_version,
                }
            )

            LOGGER.info(f"Successfully generated {len(test_scenarios)} test scenarios for: {input_data.task_title}")
            return result

        except Exception as e:
            LOGGER.error(f"Error generating test scenarios for {input_data.task_title}: {e}")
            raise Exception(f"Failed to generate test scenarios: {str(e)}") from e
