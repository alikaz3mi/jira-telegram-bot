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
    Use case for creating a user story.
    """

    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AiServiceProtocol,
    ):
        self.prompt_catalog = prompt_catalog
        self.ai_service = ai_service
        self.prompt_name = "generate_user_story"

    async def __call__(self, **kwargs) -> UserStory:
        """
        Generate a user story from raw text and project name.
        """
        spec = await self.prompt_catalog.get_prompt(self.prompt_name)
        result = await self.ai_service.run(
            prompt=spec,
            inputs=kwargs,
            cleanse_llm_text=True,
        )
        user_story = UserStory(
            summary=result["summary"],
            description=result["description"],
            components=result["components"],
            priority=result["priority"],
            story_points=result["story_points"],
        )
        return user_story
