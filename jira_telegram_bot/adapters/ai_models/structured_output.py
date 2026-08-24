"""Structured-output parsing for the prompt catalog's ``schemas`` format.

LangChain 1.x removed ``langchain.output_parsers.StructuredOutputParser`` and
``ResponseSchema``. The prompt catalog stores its schemas as plain
``{"name", "type", "description"}`` dicts, so the pieces we actually used are
reproduced here rather than reshaping every prompt to a Pydantic model.
"""
from __future__ import annotations

import json
import re
from typing import Any
from typing import Dict
from typing import List

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import BaseOutputParser

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class StructuredOutputParser(BaseOutputParser):
    """Parse a JSON object described by a list of response schemas."""

    schemas: List[Dict[str, Any]]

    @classmethod
    def from_response_schemas(
        cls,
        schemas: List[Dict[str, Any]],
    ) -> "StructuredOutputParser":
        return cls(schemas=schemas)

    def get_format_instructions(self, only_json: bool = False) -> str:
        entries = [
            (
                f'\t"{s.get("name", "result")}": {s.get("type", "string")}',
                str(s.get("description", "")).strip(),
            )
            for s in self.schemas
        ]
        lines = []
        for index, (field, description) in enumerate(entries):
            suffix = "," if index < len(entries) - 1 else ""
            comment = f"  // {description}" if description else ""
            lines.append(f"{field}{suffix}{comment}")
        body = "```json\n{\n" + "\n".join(lines) + "\n}\n```"
        if only_json:
            return body
        return (
            "The output should be a markdown code snippet formatted in the "
            "following schema, including the leading and trailing "
            '"```json" and "```":\n\n' + body
        )

    def parse(self, text: str | BaseMessage) -> Dict[str, Any]:
        if isinstance(text, BaseMessage):
            text = text.content
        candidate = text.strip()
        fenced = _JSON_FENCE.search(candidate)
        if fenced:
            candidate = fenced.group(1).strip()
        else:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start != -1 and end > start:
                candidate = candidate[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise OutputParserException(
                f"Failed to parse structured output: {exc}\nGot: {text}",
            ) from exc
        if not isinstance(parsed, dict):
            raise OutputParserException(
                f"Expected a JSON object, got {type(parsed).__name__}: {text}",
            )
        return parsed

    @property
    def _type(self) -> str:
        return "structured"
