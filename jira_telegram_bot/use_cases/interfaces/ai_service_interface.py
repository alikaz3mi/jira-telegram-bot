from abc import ABC, abstractmethod
from typing import Protocol, Dict, Any
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt

class PromptCatalog(Protocol):
    """Returns the prompt spec for a given task type & department."""
    async def get_prompt(self, task: str, department: str, user_id: str) -> "StructuredPrompt": ...

class AiService(Protocol):
    """Runs an LLM call given a prompt spec and user inputs."""
    async def run(self, prompt: "StructuredPrompt", inputs: Dict[str, Any]) -> Dict[str, Any]: ...
