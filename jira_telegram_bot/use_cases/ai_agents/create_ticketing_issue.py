from __future__ import annotations

from pathlib import Path
from typing import Dict
from typing import List

import yaml
from langchain.output_parsers import StructuredOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.openai_settings import OpenAISettings


def _load_prompt_config() -> Dict:
    """Load parse_telegram_message prompt configuration from YAML.

    Returns:
        Dictionary containing prompt configuration.

    Raises:
        FileNotFoundError: If prompt YAML file not found.
    """
    prompt_path = (
        Path(__file__).parent.parent.parent
        / "adapters"
        / "ai_models"
        / "prompts"
        / "parse_telegram_message.yaml"
    )
    with open(prompt_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_jira_prompt(content: str) -> Dict[str, str]:
    """Parse Telegram message content into structured Jira task fields using AI.

    Args:
        content: Raw message text from Telegram (supports Persian, English, mixed).

    Returns:
        Dictionary with keys:
            - summary: Concise one-line summary (max 100 chars).
            - task_type: Either "Task" or "Bug".
            - description: Full message content preserving formatting.
            - labels: List of hashtag strings extracted from message.

    Raises:
        Exception: If AI parsing fails, returns fallback values.
    """
    try:
        config = _load_prompt_config()
        settings = OpenAISettings()

        schemas = [
            {
                "name": schema["name"],
                "description": schema["description"],
                "type": schema.get("type", "string"),
            }
            for schema in config["schemas"]
        ]

        parser = StructuredOutputParser.from_response_schemas(schemas)
        format_instructions = parser.get_format_instructions()

        llm = ChatOpenAI(
            model_name=config.get("model_hint", "gpt-4o-mini"),
            openai_api_key=settings.token,
            temperature=config.get("temperature", 0.2),
        )

        prompt = PromptTemplate(
            template=config["prompt"],
            input_variables=config["input_variables"],
            partial_variables={"format_instructions": format_instructions},
        )

        chain = prompt | llm | parser

        result = chain.invoke(input={"content": content})

        labels_str = result.get("labels", "")
        labels_list = [
            label.strip() for label in labels_str.split(",") if label.strip()
        ]

        return {
            "summary": result.get("summary", ""),
            "task_type": result.get("task_type", "Task"),
            "description": result.get("description", ""),
            "labels": labels_list,
        }
    except Exception as e:
        LOGGER.error(f"Error parsing Jira prompt: {e}")
        summary = content[:80] if content else "No Summary"
        return {
            "summary": summary,
            "task_type": "Task",
            "description": content or "No description provided.",
            "labels": [],
        }
