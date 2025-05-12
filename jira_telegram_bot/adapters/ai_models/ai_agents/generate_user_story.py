from __future__ import annotations

from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AiServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator


class StoryGeneratorService(StoryGenerator):
    """
    Service for creating a structured user story.
    """

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AiServiceProtocol,
    ):
        self.prompt_catalog = prompt_catalog
        self.ai_service = ai_service
        self.prompt_name = "generate_user_story"

    async def generate(self, raw_text: str, project: str, **kwargs) -> UserStory:
        """
        Generate a user story from raw text and project name.
        
        Args:
            raw_text: The description of the work needed
            project: The project key
            **kwargs: Additional arguments like product_area, business_goal, etc.
            
        Returns:
            A structured user story
        """
        inputs = {
            "description": raw_text,
            "product_area": kwargs.get("product_area", "Software Product"),
            "business_goal": kwargs.get("business_goal", "Improve user experience"),
            "primary_persona": kwargs.get("primary_persona", "User"),
            "dependencies": kwargs.get("dependencies", "Integration with existing systems required"),
            "epic_context": kwargs.get("epic_context", ""),
            "parent_story_context": kwargs.get("parent_story_context", ""),
        }
        
        spec = await self.prompt_catalog.get_prompt(self.prompt_name)
        result = await self.ai_service.run(
            prompt=spec,
            inputs=inputs,
            cleanse_llm_text=True,
        )
        
        # Extract the user story data from the result
        story_data = result.get("user_story", {})
        
        user_story = UserStory(
            project_key=project,
            summary=story_data.get("summary", "Generated user story"),
            description=story_data.get("description", raw_text),
            components=[story_data.get("component", "")],
            priority=story_data.get("priority", "Medium"),
            story_points=story_data.get("story_points", 5),
        )
        return user_story
