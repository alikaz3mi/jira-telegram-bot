from pathlib import Path

import yaml

from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalog
from jira_telegram_bot import DEFAULT_PATH



class FilePromptCatalog(PromptCatalog):
    _BASE = DEFAULT_PATH / "jira_telegram_bot" / "adapters" / "ai_models" / "prompts"

    async def get_prompt(self, task: str, department: str = None, user_id: str = None) -> StructuredPrompt:
        file_path = self._BASE / f"{task}.yaml"
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        return StructuredPrompt(
            template=data["prompt"],
            schema=data["schema"],
            model_hint=data.get("model_hint", "gpt-4o-mini")
        )
