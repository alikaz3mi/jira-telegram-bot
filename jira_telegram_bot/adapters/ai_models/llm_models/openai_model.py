# jira_telegram_bot/adapters/openai_model.py
from __future__ import annotations

from langchain_openai import ChatOpenAI

from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.use_cases.interfaces.llm_gateway_interface import (
    LLMGatewayInterface,
)


class LLMGateway(LLMGatewayInterface):
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


class LLMModels:
    def __init__(self):
        self.models = {}

    def __getitem__(self, engine_name: str, model_name: str):
        return self.models[engine_name][[model_name]]

    def register(self, engine_name: str, model_name: str, **kwargs):
        try:
            if self.models.get(engine_name) is None:
                self.models[engine_name] = {}
            if self.models[engine_name].get(model_name) is not None:
                return

            self.models[engine_name][model_name] = (
                self.__getattribute__(f"register_{engine_name}_model")
            )(engine_name, model_name, **kwargs)
        except Exception as e:
            raise Exception(f"Unable to register embedding model. {e}")

    @staticmethod
    def register_openai_model(settings: BaseLLMModelSetting):
        return OpenAILangchainLLM(settings=settings)

    @staticmethod
    def register_gemini_model(settings: BaseLLMModelSetting):
        return GeminiLangchainLLM(settings=settings)