from __future__ import annotations

from pathlib import Path

import yaml

from jira_telegram_bot import DEFAULT_PATH, LOGGER
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)


class FilePromptCatalog(PromptCatalogProtocol):
    _BASE = (
        DEFAULT_PATH
        / "jira_telegram_bot"
        / "adapters"
        / "ai_models"
        / "prompts"
    )
    
    async def get_prompt(
        self,
        task: str,
        department: str = None,
        user_id: str = None,
    ) -> StructuredPrompt:
        try: 
            file_path = self._BASE / f"{task}.yaml"
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            
            # Convert schemas to proper format for StructuredPrompt
            schemas = []
            if "schemas" in data:
                for schema in data["schemas"]:
                    schemas.append({
                        "name": schema.get("name", "result"),
                        "type": schema.get("type", "object"),
                        "description": schema.get("description", ""),
                        **{k: v for k, v in schema.items() if k not in ["name", "type", "description"]}
                    })
            
            return StructuredPrompt(
                id=data.get("id"),
                description=data.get("description", ""),
                version=data.get("version", "1.0"),
                language=data.get("language", "en"),
                template=data["prompt"],
                schemas=schemas,
                ai_model_hint=data["model_hint"],
                ai_model_engine=data["model_engine"],
                temperature=data.get("temperature", 0.3),
                few_shots=data.get("few_shots", []),
                input_variables=data.get("input_variables", []),
            )
        except Exception as e:
            LOGGER.error(f"Error loading prompt {task}: {e}")
            raise ValueError(f"Prompt {task} not found or invalid format.")
