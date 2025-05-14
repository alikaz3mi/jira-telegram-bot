"""Service for summarizing board tasks grouped by components and epics."""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.output_parsers import StrOutputParser

from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AiServiceProtocol
from jira_telegram_bot.use_cases.interfaces.board_summarizer_service_interface import (
    BoardSummarizerServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)


class BoardSummarizerService(BoardSummarizerServiceInterface):
    """Service for summarizing board tasks grouped by component and epic."""

    def __init__(
        self, 
        prompt_catalog: PromptCatalogProtocol, 
        ai_service: AiServiceProtocol
    ) -> None:
        """Initialize the service with dependencies.

        Args:
            prompt_catalog: Repository of prompt templates
            ai_service: Service to interact with AI models
        """
        self._prompt_catalog = prompt_catalog
        self._ai_service = ai_service
        self._output_parser = StrOutputParser()

    async def run(self, grouped_tasks: str) -> str:
        """Generate a summary of tasks grouped by component and epic.

        Args:
            grouped_tasks: String representation of grouped tasks data

        Returns:
            A formatted summary text in Persian
        """
        prompt = self._prompt_catalog.get_prompt("board_summarizer")
        llm = self._ai_service.get_llm(
            model_hint=prompt.model_hint, 
            temperature=prompt.temperature
        )
        
        chain = prompt.prompt | llm | self._output_parser
        
        result = await chain.ainvoke({"grouped_tasks": grouped_tasks})
        
        return result