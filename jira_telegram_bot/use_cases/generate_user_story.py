from __future__ import annotations

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.entities.user_story_generation_request import UserStoryGenerationRequest
from jira_telegram_bot.use_cases.ai_agents.agent_generate_use_story import AgentGenerateUserStory

class GenerateUserStoryUseCase:
    """
    Use case for creating a user story using AI agents.
    """

    def __init__(self, ai_generate_user_story: AgentGenerateUserStory):
        """Initialize with AI agent use case.
        
        Args:
            ai_generate_user_story: AI agent use case for generating user stories.
        """
        self.ai_generate_user_story = ai_generate_user_story

    async def generate(self, raw_text: str, project: str, **kwargs) -> UserStory:
        """Generate a user story from raw text and project.
        
        Args:
            raw_text: Raw text describing the requirement.
            project: Project key.
            **kwargs: Additional optional parameters.
            
        Returns:
            Generated user story.
        """
        # Create input for AI agent
        input_data = GenerateUserStoryInput(
            raw_text=raw_text,
            project_key=project,
            project_context=kwargs.get('product_area'),
        )
        
        # Execute AI agent use case
        result = await self.ai_generate_user_story.execute(input_data)
        
        # Convert AI result to UserStory entity
        return UserStory(
            project_key=project,
            summary=result.user_story.summary,
            description=result.user_story.description,
            components=result.user_story.components,
            labels=result.user_story.labels,
            story_points=float(result.user_story.story_points or 3),
            priority=result.user_story.priority,
            task_type="Story",
            epic_link=result.user_story.epic_link,
            assignee=result.user_story.assignee_suggestion,
        )

    async def __call__(self, request: UserStoryGenerationRequest) -> UserStory:
        """Generate a user story from the provided request.
        
        Args:
            request: User story generation request entity.
            
        Returns:
            Generated user story.
        """
        # Create input for AI agent
        input_data = GenerateUserStoryInput(
            raw_text=request.raw_text,
            project_key=request.project,
            project_context=request.product_area,
        )
        
        # Execute AI agent use case
        result = await self.ai_generate_user_story.execute(input_data)
        
        # Convert AI result to UserStory entity
        return UserStory(
            project_key=request.project,
            summary=result.user_story.summary,
            description=result.user_story.description,
            components=result.user_story.components,
            labels=result.user_story.labels,
            story_points=float(result.user_story.story_points or 3),
            priority=result.user_story.priority,
            task_type="Story",
            epic_link=result.user_story.epic_link,
            assignee=result.user_story.assignee_suggestion,
        )
