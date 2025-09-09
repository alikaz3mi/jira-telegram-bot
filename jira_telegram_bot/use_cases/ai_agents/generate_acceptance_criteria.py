"""Generate acceptance criteria AI agent use case."""

from __future__ import annotations

from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.ai_agent_models.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaInput,
)
from jira_telegram_bot.entities.ai_agent_models.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaResult,
)
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase


class GenerateAcceptanceCriteriaUseCase(BaseAIAgentUseCase):
    """AI agent use case for generating user story and acceptance criteria."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the generate acceptance criteria use case.

        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.GENERATE_ACCEPTANCE_CRITERIA

    async def execute(
        self,
        input_data: GenerateAcceptanceCriteriaInput,
        robot_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> GenerateAcceptanceCriteriaResult:
        """Execute acceptance criteria generation from input data.

        Args:
            input_data: Input data containing task details and context.
            robot_id: Optional robot/user ID for prompt customization.
            prompt_version: Optional prompt version (unused for now).

        Returns:
            Generated acceptance criteria result with user story and delivery process.

        Raises:
            Exception: If AI service processing fails.
        """
        try:
            LOGGER.info(f"Generating acceptance criteria for task: {input_data.task_title}")

            # Prepare input variables for the prompt
            prompt_inputs = {
                "task_title": input_data.task_title,
                "task_description": input_data.task_description or "",
                "epic_name": input_data.epic_name or "مشخص نشده",
                "related_departments": ", ".join(input_data.related_departments) 
                    if input_data.related_departments else "مشخص نشده",
                "project_info": input_data.project_info or "",
                "special_requirements": input_data.special_requirements or "",
            }

            # Process with AI service
            ai_response = await self._process_with_ai(
                inputs=prompt_inputs,
                department=None,
                user_id=robot_id,
            )

            # Parse AI response
            result_data = ai_response.get("result", {})
            
            result = GenerateAcceptanceCriteriaResult(
                user_story=result_data.get("user_story", ""),
                acceptance_criteria=result_data.get("acceptance_criteria", []),
                delivery_process=result_data.get("delivery_process", []),
                metadata={
                    "task_title": input_data.task_title,
                    "epic_name": input_data.epic_name,
                    "departments": input_data.related_departments,
                    "ai_model": "4o-mini",
                    "prompt_version": prompt_version,
                }
            )

            LOGGER.info(f"Successfully generated acceptance criteria for: {input_data.task_title}")
            return result

        except Exception as e:
            LOGGER.error(f"Error generating acceptance criteria for {input_data.task_title}: {e}")
            raise Exception(f"Failed to generate acceptance criteria: {str(e)}") from e
