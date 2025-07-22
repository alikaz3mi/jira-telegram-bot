"""Use case for decomposing user stories into tasks."""

from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.entities.ai_agent_models.story_decomposition import StoryDecompositionInput
from jira_telegram_bot.entities.ai_agent_models.story_decomposition import StoryDecompositionResult
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase


class StoryDecompositionUseCase(BaseAIAgentUseCase):
    """Use case for decomposing user stories into smaller tasks."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the story decomposition use case.
        
        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.DECOMPOSE_USER_STORY

    async def execute(
        self,
        project_context: str,
        description: str,
        departments: str,
        department_details: str,
        assignee_details: str,
    ) -> Dict[str, Any]:
        """Break down a user story into smaller tasks.
        
        Args:
            project_context: Context and information about the project.
            description: Description of the work needed.
            departments: List of available departments/components.
            department_details: Detailed information about each department.
            assignee_details: Information about team members and their roles.
            
        Returns:
            Dictionary containing the decomposed story with subtasks.
        """
        # Prepare input data
        input_data = StoryDecompositionInput(
            project_context=project_context,
            description=description,
            departments=departments,
            department_details=department_details,
            assignee_details=assignee_details,
        )

        # Convert to dictionary for AI service
        ai_inputs = {
            "project_context": project_context,
            "description": description,
            "departments": departments,
            "department_details": department_details,
            "assignee_details": assignee_details,
        }

        # Process with AI service
        result = await self._process_with_ai(ai_inputs, cleanse_llm_text=False)
        
        return result
