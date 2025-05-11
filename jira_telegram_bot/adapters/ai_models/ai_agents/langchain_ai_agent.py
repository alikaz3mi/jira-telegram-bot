from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser

from jira_telegram_bot.entities.structured_prompt import StructuredPrompt

from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AiService

_MODEL_REGISTRY = {
    "o3": ChatGoogleGenerativeAI(model_name="o3"),
    "4o-mini": ChatGoogleGenerativeAI(model_name="4o-mini"),
}

_DEFAULT_MODEL = _MODEL_REGISTRY["4o-mini"]

class LangChainAiService(AiService):
    def __init__(self, model_registery):
    async def run(self, prompt: StructuredPrompt, inputs: dict) -> dict:
        model = _MODEL_REGISTRY.get(prompt.model_hint, _DEFAULT_MODEL)

        parser = StructuredOutputParser.from_response_schemas(
            list(prompt.schema["fields"])
        )
        tmpl = PromptTemplate(
            template=prompt.template,
            input_variables=list(inputs.keys()),
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = tmpl | model | parser
        return await chain.ainvoke(inputs)

    # TODO: register chains for re-usage and no re-creation