from __future__ import annotations

from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator


class GenerateUserStoryUseCase:
    """
    Use case for creating a user story.
    """

    def __init__(self, story_generator: StoryGenerator):
        self.story_generator = story_generator

    async def __call__(self, raw_text: str, project: str) -> UserStory:
        """
        Generate a user story from raw text and project name.
        """
        user_story = await self.story_generator.generate(
            raw_text=raw_text,
            project=project,
        )
        return user_story
