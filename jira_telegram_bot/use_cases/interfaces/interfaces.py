from __future__ import annotations

from typing import Protocol

from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.entities.task import UserStory


class StoryGeneratorInterface(Protocol):
    async def generate(self, raw_text: str, project: str, **kwargs) -> UserStory:
        ...


class TaskSplitterInterface(Protocol):
    async def split(self, story: UserStory, project: str) -> list[TaskData]:
        ...


class IssueTrackerInterface(Protocol):
    async def create_story(self, story: UserStory) -> str:
        pass

    async def create_subtask(self, parent_id: str, task: TaskData) -> str:
        pass
