from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List

from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AiServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.subtask_creation_interface import SubtaskCreationInterface


class SubtaskCreationService(SubtaskCreationInterface):
    """Service for creating subtasks from a parent story."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AiServiceProtocol,
    ):
        self.prompt_catalog = prompt_catalog
        self.ai_service = ai_service
        self.prompt_name = "create_subtasks"

    async def create_subtasks(
        self,
        project_context: str,
        description: str,
        departments: str,
        department_details: str,
        assignee_details: str,
    ) -> Dict[str, Any]:
        """
        Create subtasks based on a parent story description.
        
        Args:
            project_context: Context and information about the project
            description: Description of the work needed
            departments: List of available departments/components
            department_details: Detailed information about each department
            assignee_details: Information about team members and their roles
            
        Returns:
            Dictionary containing the created subtasks
        """
        spec = await self.prompt_catalog.get_prompt(self.prompt_name)
        result = await self.ai_service.run(
            prompt=spec,
            inputs={
                "project_context": project_context,
                "description": description,
                "departments": departments,
                "department_details": department_details,
                "assignee_details": assignee_details,
            },
            cleanse_llm_text=True,
        )
        return result
