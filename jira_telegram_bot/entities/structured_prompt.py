from pydantic import Field, BaseModel
from typing import Dict, Any


class StructuredPrompt(BaseModel):
    schema: Dict[str, Any] = Field(description="Schema for the structured output.")
    template: str = Field(description="Prompt template with placeholders for user inputs.")
    model_hint: str = Field(default="gpt-4o-mini", description="Optional model hint for the LLM.")
