"""AI agent use case for creating subtasks from a parent story."""

from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot.entities.ai_agent_models.create_subtasks import CreateSubtasksInput
from jira_telegram_bot.entities.ai_agent_models.create_subtasks import CreateSubtasksResult
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AIServiceProtocol,
    PromptCatalogProtocol,
)
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase


class CreateSubtasksUseCase(BaseAIAgentUseCase):
    """Use case for creating subtasks from a parent story using AI."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the create subtasks use case.
        
        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.CREATE_SUBTASKS

    async def execute(
        self,
        input_data: CreateSubtasksInput,
    ) -> CreateSubtasksResult:
        """Execute the create subtasks use case.
        
        Args:
            input_data: Input data for creating subtasks
            
        Returns:
            Result containing the created subtasks
        """
        # Convert to dictionary for AI service
        ai_inputs = {
            "project_context": input_data.project_context,
            "description": input_data.description,
            "departments": input_data.departments,
            "department_details": input_data.department_details,
            "assignee_details": input_data.assignee_details,
        }

        # Process with AI service
        result = await self._process_with_ai(ai_inputs, cleanse_llm_text=True)
        
        # Parse result into CreateSubtasksResult
        # Note: The AI service should return data matching our schema
        return CreateSubtasksResult(**result)

    async def create_subtasks(
        self,
        project_context: str,
        description: str,
        departments: str,
        department_details: str,
        assignee_details: str,
    ) -> Dict[str, Any]:
        """Create subtasks based on a parent story description.
        
        This method provides the interface expected by SubtaskCreationInterface.
        
        Args:
            project_context: Context and information about the project
            description: Description of the work needed
            departments: List of available departments/components
            department_details: Detailed information about each department
            assignee_details: Information about team members and their roles
            
        Returns:
            Dictionary containing the created subtasks
        """
        # Prepare input data
        input_data = CreateSubtasksInput(
            project_context=project_context,
            description=description,
            departments=departments,
            department_details=department_details,
            assignee_details=assignee_details,
        )

        # Execute the use case
        result = await self.execute(input_data)
        
        # Convert back to dictionary for interface compatibility
        return result.model_dump()
