from __future__ import annotations

from langchain_openai.chat_models import ChatOpenAI

from jira_telegram_bot.settings import OPENAI_SETTINGS


class Statistics:
    def __init__(
        self,
    ):
        self.load_ai_model()

    def load_ai_model(self):
        return ChatOpenAI(
            api_key=OPENAI_SETTINGS.token,
            model="gpt-4o-mini",
        )

    def __call__(self, query: str):
        pass
