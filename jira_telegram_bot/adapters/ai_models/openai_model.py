# jira_telegram_bot/adapters/openai_model.py
from __future__ import annotations

from langchain_openai import ChatOpenAI

from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.use_cases.interface.openai_gateway_interface import (
    OpenAIGatewayInterface,
)


class OpenAIGateway(OpenAIGatewayInterface):
    """
    Concrete adapter for calling OpenAI or LangChain-based LLMs.
    """

    def __init__(self):
        self.api_key = OPENAI_SETTINGS.token  # or similar
        self.temperature = 0.2
        # etc.

    def get_llm(self) -> ChatOpenAI:
        """
        Returns a ChatOpenAI client or some LLM object.
        """
        llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            openai_api_key=self.api_key,
            temperature=self.temperature,
        )
        return llm
