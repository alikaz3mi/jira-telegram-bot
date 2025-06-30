"""Generate user story AI agent use case."""

from __future__ import annotations

from typing import Dict
from typing import Optional

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryResult
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import UserStoryCandidate
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase


class GenerateUserStoryUseCase(BaseAIAgentUseCase):
    """AI agent use case for generating user stories from raw text input."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the generate user story use case.

        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.GENERATE_USER_STORY

    async def execute(
        self,
        input_data: GenerateUserStoryInput,
        robot_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> GenerateUserStoryResult:
        """Execute user story generation from input data.

        Args:
            input_data: Input data containing raw text and context.
            robot_id: Optional robot/user ID for prompt customization.
            prompt_version: Optional prompt version (unused for now).

        Returns:
            Generated user story result with metadata.

        Raises:
            Exception: If AI processing fails or validation errors occur.
        """
        # Prepare prompt inputs from the input data
        prompt_inputs = self._prepare_prompt_inputs(input_data)
        
        # Process with AI service using the base class method
        ai_result = await self._process_with_ai(
            inputs=prompt_inputs,
            user_id=robot_id,
        )
        
        # Parse and validate the AI result
        return self._parse_ai_result(ai_result, input_data)

    def _prepare_prompt_inputs(self, input_data: GenerateUserStoryInput) -> Dict[str, str]:
        """Prepare inputs for the AI prompt from input data.

        Args:
            input_data: Input data for user story generation.

        Returns:
            Dictionary of prompt inputs.
        """
        # Format available components and epics for context
        components_text = self._format_components(input_data.available_components)
        epics_text = self._format_epics(input_data.available_epics)
        sprint_text = self._format_sprint_info(input_data.current_sprint_info)
        
        return {
            "product_area": input_data.project_context or f"Project {input_data.project_key}",
            "business_goal": "Deliver value to users and stakeholders",
            "primary_persona": "System User",
            "dependencies": f"Components: {components_text}, Sprint: {sprint_text}",
            "description": input_data.raw_text,
            "epic_context": epics_text,
            "parent_story_context": "",
        }

    def _parse_ai_result(
        self,
        ai_result: Dict,
        input_data: GenerateUserStoryInput,
    ) -> GenerateUserStoryResult:
        """Parse AI service result into structured output.

        Args:
            ai_result: Raw result from AI service.
            input_data: Original input data for context.

        Returns:
            Structured user story result.

        Raises:
            ValueError: If AI result is invalid or missing required fields.
        """
        if "user_story" not in ai_result:
            raise ValueError("AI result missing 'user_story' field")
        
        user_story_data = ai_result["user_story"]
        
        # Validate required fields
        if not user_story_data.get("summary"):
            raise ValueError("AI result missing user story summary")
        if not user_story_data.get("description"):
            raise ValueError("AI result missing user story description")
        
        # Create the main user story candidate
        user_story_candidate = UserStoryCandidate(
            summary=user_story_data["summary"],
            description=user_story_data["description"],
            story_points=user_story_data.get("story_points", 3),
            priority=user_story_data.get("priority", "Medium"),
            components=[user_story_data.get("component")] if user_story_data.get("component") else [],
        )
        
        return GenerateUserStoryResult(
            user_story=user_story_candidate,
            confidence_score=0.85,  # Default confidence score
            reasoning="Generated using AI analysis of requirements and project context",
            processing_metadata={
                "prompt_used": self.prompt_name,
                "input_project": input_data.project_key,
                "raw_ai_result": ai_result,
            },
        )

    def _format_components(self, components: list[str]) -> str:
        """Format available components for the prompt.

        Args:
            components: List of available components.

        Returns:
            Formatted string of components.
        """
        if not components:
            return "No specific components defined"
        return ", ".join(components)

    def _format_epics(self, epics: list[Dict]) -> str:
        """Format available epics for the prompt.

        Args:
            epics: List of available epics.

        Returns:
            Formatted string describing epics.
        """
        if not epics:
            return "No active epics"
        
        epic_descriptions = []
        for epic in epics:
            epic_desc = f"- {epic.get('key', 'UNKNOWN')}: {epic.get('summary', 'No summary')}"
            epic_descriptions.append(epic_desc)
        
        return "Available Epics:\n" + "\n".join(epic_descriptions)

    def _format_sprint_info(self, sprint_info: Optional[Dict]) -> str:
        """Format current sprint information for the prompt.

        Args:
            sprint_info: Current sprint information.

        Returns:
            Formatted string describing sprint.
        """
        if not sprint_info:
            return "No active sprint"
        
        sprint_name = sprint_info.get("name", "Unknown Sprint")
        sprint_goal = sprint_info.get("goal", "No goal defined")
        
        return f"{sprint_name} (Goal: {sprint_goal})"