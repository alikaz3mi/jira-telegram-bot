from __future__ import annotations

from typing import Any
from typing import Dict

from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser
from langchain.prompts import PromptTemplate

from jira_telegram_bot.adapters.ai_models.utils import llm_result_correction_chain
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AiServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.llm_model_interface import LLMModelInterface


class LangChainAiService(AiServiceProtocol):
    def __init__(self, model_registry: LLMModelInterface):
        self.model_registry = model_registry

    async def run(
        self,
        prompt: StructuredPrompt,
        inputs: dict,
        cleanse_llm_text: bool = False,
    ) -> Dict[str, Any]:
        # TODO: get a model with the least used RPM and RPD. Or, that has at least 10% of the max RPM and RPD
        model = self.model_registry[prompt.ai_model_hint, prompt.ai_model_engine]
        parser = StructuredOutputParser.from_response_schemas(
            [ResponseSchema(**schema) for schema in prompt.schemas],
        )
        tmpl = PromptTemplate(
            template=prompt.template,
            input_variables=prompt.input_variables,
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = await self.create_chain(cleanse_llm_text, model, parser, tmpl)
        return await chain.with_config(
            configurable={"llm_temperature": prompt.temperature},
        ).ainvoke(inputs)

    @staticmethod
    async def create_chain(cleanse_llm_text: bool, model, parser, tmpl: PromptTemplate):
        if cleanse_llm_text:
            chain = tmpl | model | llm_result_correction_chain | parser
        else:
            chain = tmpl | model | parser
        return chain

    # TODO: register chains for re-usage and no re-creation
