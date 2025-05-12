from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List

from pydantic import BaseModel
from pydantic import Field


class StructuredPrompt(BaseModel):
    schemas: List[Dict[str, Any]] = Field(
        description="Schema for the structured output.",
    )
    template: str = Field(
        description="Prompt template with placeholders for user inputs.",
    )
    model_hint: str = Field(
        default="gpt-4o-mini",
        description="Optional model hint for the LLM.",
    )
    model_engine: str = Field(
        default="openai",
        description="Optional model engine for the LLM.",
    )
    few_shots: List[str] = Field(
        description="Optional few-shot examples to guide the model's response.",
    )
    temperature: float = Field(
        default=0.3,
        description="Temperature setting for the LLM.",
    )
    input_variables: List[str] = Field(
        description="Input variables for the prompt template.",
    )
