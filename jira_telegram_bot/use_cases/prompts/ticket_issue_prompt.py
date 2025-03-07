from __future__ import annotations

from typing import Dict

from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from jira_telegram_bot.settings import OPENAI_SETTINGS


def parse_jira_prompt(content: str) -> Dict[str, str]:
    """
    Uses a LangChain LLM prompt to parse the content and produce a JSON string
    with 'summary', 'task_type', and 'description'. Then returns it as a dict.
    """

    schema = [
        ResponseSchema(
            name="task_info",
            description="A JSON object containing summary, task_type, label, and description fields. Example: {'summary': 'Task summary', 'task_type': 'Bug', 'description': 'Task description', 'label': '#ID121'}",
            type="json",
        ),
    ]

    parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = parser.get_format_instructions()

    template_text = """
                    You are given the following content from a user:

                    {content}

                    Your job is to analyze this content and provide structured output for creating a task for jira.
                    keep the same language as the content.


                    {format_instructions}

                    Instructions:
                    1. "task_type": The type of task must only be Task or Bug.
                    2. "summary": the summary must be a single line. with the same language as content. If exists in content, keep #ID number in the summary.
                    3. "description": the description must be a single line. with the same language as content.
                    4. "label": label is the #ID if the content has it.
                    """

    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        openai_api_key=OPENAI_SETTINGS.token,
        temperature=0.2,
    )
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
    except Exception as e:
        return {
            "summary": "No Summary",
            "task_type": "Task",
            "description": content or "No description provided.",
        }
