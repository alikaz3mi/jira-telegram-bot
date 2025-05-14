from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Protocol

from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AiServiceProtocol,
    PromptCatalogProtocol,
)


class StoryDecompositionInterface(Protocol):
    """Interface for decomposing user stories into tasks and subtasks."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AiServiceProtocol,
    ):
        """
        Initialize the StoryDecompositionInterface with a prompt catalog and AI service.
        
        Args:
            prompt_catalog: Catalog of prompts for AI service
            ai_service: AI service to process the prompts
        """
        ...

    async def decompose_story(
        self,
        project_context: str,
        description: str,
        departments: str,
        department_details: str,
        assignee_details: str,
    ) -> Dict[str, Any]:
        """
        Break down a user story into smaller tasks.
        
        Args:
            project_context: Context and information about the project
            description: Description of the work needed
            departments: List of available departments/components
            department_details: Detailed information about each department
            assignee_details: Information about team members and their roles
            
        Returns:
            Dictionary containing the decomposed story with subtasks
        """
        ...
