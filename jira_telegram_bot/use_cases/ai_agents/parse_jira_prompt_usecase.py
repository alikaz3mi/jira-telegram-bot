from __future__ import annotations

from typing import Dict

from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser
from langchain.prompts import PromptTemplate

from jira_telegram_bot.use_cases.interfaces.openai_gateway_interface import (
    OpenAIGatewayInterface,
)


class ParseJiraPromptUseCase:
    """
    Use case for parsing freeform user text into structured Jira fields
    via an LLM (OpenAI).
    """

    def __init__(self, openai_gateway: OpenAIGatewayInterface):
        self._openai_gateway = openai_gateway

    def run(self, content: str) -> Dict[str, str]:
        schema = [
            ResponseSchema(
                name="task_info",
                description=(
                    "A JSON object containing summary, task_type, label, and description fields."
                ),
                type="json",
            ),
        ]
        parser = StructuredOutputParser.from_response_schemas(schema)
        format_instructions = parser.get_format_instructions()

        template_text = """
            You are given the following content from a user:

            {content}

            Your job is to analyze this content and provide structured output for creating a task for Jira.
            Keep the same language as the content.

            {format_instructions}

            Instructions:
            1. "task_type": must only be Task or Bug.
            2. "summary": single line. If #ID is in content, keep it.
            3. "description": single line.
            4. "label": #ID if content has it.
        """

        llm = self._openai_gateway.get_llm()

        prompt = PromptTemplate(
            template=template_text,
            input_variables=["content"],
            partial_variables={"format_instructions": format_instructions},
        )
        chain = prompt | llm | parser
        result = chain.invoke(input={"content": content})

        try:
            return {
                "summary": result["task_info"].get("summary", ""),
                "task_type": result["task_info"].get("task_type", "Task"),
                "description": result["task_info"].get("description", ""),
                "labels": result["task_info"].get("label", ""),
            }
        except Exception:
            return {
                "summary": "No Summary",
                "task_type": "Task",
                "description": content or "No description provided.",
            }
