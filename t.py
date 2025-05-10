from pathlib import Path
import yaml
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
load_dotenv()


from parschat_logic.use_cases.interfaces.base_prompt import BasePrompt
from parschat_logic.use_cases.interfaces.base_prompt import PromptTemplate
from parschat_logic.use_cases.interfaces.base_prompt import ResponseSchema
from parschat_logic.use_cases.interfaces.base_prompt import StructuredOutputParser


class SelectImportantCategories(BasePrompt):
    prompt = """A list of categories has been given to you.
Imagine you are a professional seller who wants to fully understand the products sold in the store based on their \
categories and guide customers in their purchases.

Follow these INSTRUCTIONS strictly:
- Classify the categories into Important categories.
- If the category is not important, classify it as "سایر موارد".
- Ensure the language of categories are in persian.
- {format_instructions}


### Here is the Given Data ###
{categories}
"""
    schema = [
        ResponseSchema(
            name="categories",
            description="""array of identified categories in the following format: [
    {{
        "new_category": "string",
        "initial_categories": [
            "category1",
            "category2",
            "category3"
        ]
    }}
]""",
            type="array(object)",
        ),
    ]
    parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = parser.get_format_instructions()
    template = PromptTemplate(
        template=prompt,
        input_variables=["categories"],
        partial_variables={"format_instructions": format_instructions},
    )

# 1. load YAML
raw = yaml.safe_load(
    Path("x.yaml").read_text(encoding="utf-8")
)

# 2. build parser & prompt
schemas = [ResponseSchema(**sch) for sch in raw["schemas"]]
parser = StructuredOutputParser.from_response_schemas(schemas)
prompt_tmpl = PromptTemplate(
    template=raw["prompt"],
    input_variables=["categories"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# 3. run chain
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("gemini_connection_config_token"))
chain = prompt_tmpl | llm | parser
chain_2 = SelectImportantCategories.template | llm | SelectImportantCategories.parser
result_2 = chain_2.invoke(
    {"categories": "لبنیات\nماست\nپنیر\nکفش ورزشی\nتلفن همراه\nپاوربانک"}
)

print(result_2)

result = chain.invoke(
    {"categories": "لبنیات\nماست\nپنیر\nکفش ورزشی\nتلفن همراه\nپاوربانک"}
)

print(result)



