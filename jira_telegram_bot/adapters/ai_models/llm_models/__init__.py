from __future__ import annotations

from langchain_core.runnables import ConfigurableField
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from jira_telegram_bot.settings.gemini_settings import GeminiConnectionSetting
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.use_cases.interfaces.llm_model_interface import (
    LLMModelInterface,
)


class LLMModels(LLMModelInterface):
    def __init__(
        self,
        openai_settings: OpenAISettings,
        gemini_settings: GeminiConnectionSetting,
    ):
        self.models = {}
        self.openai_settings = openai_settings
        self.gemini_settings = gemini_settings

    def __getitem__(self, engine_name: str, model_name: str):
        # TODO: In here, create the algorithm and caching to return the model with the least used RPM and RPD,
        #  or 10% of the max RPM and RPD
        try:
            return self.models[engine_name][[model_name]]
        except KeyError:
            self.register(engine_name, model_name)
            return self.models[engine_name][model_name]
        except Exception as e:
            raise Exception(f"Unable to get embedding model. {e}")

    def register(self, engine_name: str, model_name: str, **kwargs):
        try:
            if self.models.get(engine_name) is None:
                self.models[engine_name] = {}
            if self.models[engine_name].get(model_name) is not None:
                return

            self.models[engine_name][model_name] = (
                self.__getattribute__(f"register_{engine_name}_model")
            )(model_name, **kwargs)
        except Exception as e:
            raise Exception(f"Unable to register embedding model. {e}")

    def register_openai_model(self, model_name: str):
        # TODO: create models by the number of tokens
        return ChatOpenAI(
            model=model_name,
            api_key=self.openai_settings.token,
        ).configurable_fields(
            temperature=ConfigurableField(
                id="llm_temperature",
                name="LLM Temperature",
                description="The temperature of the LLM",
            ),
        )

    def register_gemini_model(self, model_name: str):
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.gemini_settings.token,
        ).configurable_fields(
            temperature=ConfigurableField(
                id="llm_temperature",
                name="LLM Temperature",
                description="The temperature of the LLM",
            ),
        )
