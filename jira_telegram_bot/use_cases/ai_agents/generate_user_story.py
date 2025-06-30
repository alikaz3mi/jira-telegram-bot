"""AI agent use case for generating user stories from raw text."""

from __future__ import annotations

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryResult
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import UserStoryCandidate
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase


class GenerateUserStoryUseCase(BaseAIAgentUseCase):
    """Use case for generating user stories using AI agents."""

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the generate user story use case.

        Args:
            prompt_catalog: Protocol for loading prompt templates.
            ai_service: Protocol for AI service interactions.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.GENERATE_USER_STORY

    async def execute(
        self,
        input_data: GenerateUserStoryInput,
        robot_id: str = None,
        prompt_version: str = None,
    ) -> GenerateUserStoryResult:
        """Execute user story generation from raw text input.

        Args:
            input_data: Input data containing raw text and context.
            robot_id: Optional robot/user ID for prompt customization.
            prompt_version: Optional prompt version (unused, for interface compatibility).

        Returns:
            Generated user story with metadata and alternatives.

        Raises:
            Exception: If AI processing fails or validation errors occur.
        """
        # Format input context for the AI prompt
        components_text = self._format_components(input_data.available_components)
        epics_text = self._format_epics(input_data.available_epics)
        sprint_text = self._format_sprint_info(input_data.current_sprint_info)
        
        # Prepare inputs for the AI prompt template
        prompt_inputs = {
            "product_area": input_data.project_context or f"Project {input_data.project_key}",
            "business_goal": "Deliver value to users and stakeholders",
            "primary_persona": "System User",
            "dependencies": f"Components: {components_text}, Sprint: {sprint_text}",
            "description": input_data.raw_text,
            "epic_context": epics_text,
            "parent_story_context": "",
        }
        
        # Process with AI service
        ai_result = await self._process_with_ai(
            inputs=prompt_inputs,
            user_id=robot_id,
        )
        
        # Parse and validate AI response
        user_story_data = ai_result.get("user_story", {})
        
        if not user_story_data:
            raise ValueError("AI service returned empty user story data")
        
        # Create the main user story candidate
        user_story_candidate = UserStoryCandidate(
            summary=user_story_data.get("summary", ""),
            description=user_story_data.get("description", ""),
            story_points=user_story_data.get("story_points", 3),
            priority=user_story_data.get("priority", "Medium"),
            components=[user_story_data.get("component")] if user_story_data.get("component") else [],
            labels=[],  # Can be enhanced based on AI output
            epic_link=None,  # Can be enhanced based on epic matching
            assignee_suggestion=None,  # Can be enhanced based on component mapping
        )
        
        # Return structured result
        return GenerateUserStoryResult(
            user_story=user_story_candidate,
            confidence_score=0.8,  # Default confidence, can be enhanced
            reasoning="Generated based on AI analysis of requirements and project context",
            alternative_suggestions=[],  # Can be enhanced with multiple candidates
            processing_metadata={
                "model_used": "AI service",
                "prompt_name": self.prompt_name,
                "input_tokens": len(input_data.raw_text.split()),
                "project_key": input_data.project_key,
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

    def _format_epics(self, epics: list[dict]) -> str:
        """Format available epics for the prompt.

        Args:
            epics: List of available epics with key and summary.

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

    def _format_sprint_info(self, sprint_info: dict | None) -> str:
        """Format current sprint information for the prompt.

        Args:
            sprint_info: Current sprint information with name and goal.

        Returns:
            Formatted string describing sprint.
        """
        if not sprint_info:
            return "No active sprint"
        
        sprint_name = sprint_info.get("name", "Unknown Sprint")
        sprint_goal = sprint_info.get("goal", "No goal defined")
        
        return f"{sprint_name} (Goal: {sprint_goal})"
