"""Input and output models for board summarization."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot.entities.task import TaskData


class BoardSummarizerInput(BaseModel):
    """Input model for board summarization."""
    
    tasks: List[TaskData] = Field(description="List of tasks to summarize")


class BoardSummarizerResult(BaseModel):
    """Result model for board summarization."""
    
    summary: str = Field(description="Formatted summary text for the board tasks")
