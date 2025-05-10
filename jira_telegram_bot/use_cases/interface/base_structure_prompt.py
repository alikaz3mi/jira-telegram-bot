from typing import List
from pydantic import Field
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser
from langchain.output_parsers import ResponseSchema


class StructuredPromptSpec:
    prompt: str = Field()
    schemas: List[ResponseSchema] = Field()
    format_instructions: str = Field(
        description="The output of parser.get_format_instructions()"
    )
    template: PromptTemplate = Field(
        description="Runnable used at the beginning of the chain."
    )
    parser: StructuredOutputParser = Field(
        description="Runnable used at the end of the chain."
    )