from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Protocol

from jira_telegram_bot.entities.structured_prompt import StructuredPrompt


class PromptCatalogProtocol(Protocol):
    """Returns the prompt spec for a given task type & department."""

    async def get_prompt(
        self,
        task: str,
        department: str = None,
        user_id: str = None,
    ) -> StructuredPrompt:
        pass


class AiServiceProtocol(Protocol):
    """Runs an LLM call given a prompt spec and user inputs."""

    async def run(
        self,
        prompt: "StructuredPrompt",
        inputs: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        pass
