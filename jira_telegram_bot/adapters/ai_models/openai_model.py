# jira_telegram_bot/adapters/openai_model.py
from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.use_cases.interfaces.llm_interface import LLMInterface


class OpenAIGateway(LLMInterface):
    """
    Concrete adapter for calling OpenAI language models via API.
    """

    def __init__(self):
        """Initialize the OpenAI gateway with API settings."""
        self.api_key = OPENAI_SETTINGS.token
        self.temperature = 0.2
        self.client = AsyncOpenAI(api_key=self.api_key)
        
    def get_llm(self) -> ChatOpenAI:
        """
        Returns a ChatOpenAI client for use with LangChain.
        
        Returns:
            A ChatOpenAI language model instance.
        """
        return ChatOpenAI(
            model_name="gpt-4o-mini",
            openai_api_key=self.api_key,
            temperature=self.temperature,
        )
    
    async def generate_text(
        self, prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using the OpenAI API directly.
        
        Args:
            prompt: The prompt to send to the model.
            temperature: Controls randomness (lower is more deterministic).
            max_tokens: Maximum number of tokens to generate.
            
        Returns:
            Generated text as string.
        """
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    
    async def generate_structured_output(
        self, prompt: str, output_schema: Dict[str, Any], temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Generate structured output according to the given schema using OpenAI's function calling.
        
        Args:
            prompt: The prompt to send to the model.
            output_schema: The schema that defines the expected output structure.
            temperature: Controls randomness (lower is more deterministic).
            
        Returns:
            Structured output as dictionary.
        """
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            functions=[{"name": "extract_data", "parameters": output_schema}],
            function_call={"name": "extract_data"},
            temperature=temperature,
        )
        
        function_call = response.choices[0].message.function_call
        if function_call and function_call.arguments:
            import json
            return json.loads(function_call.arguments)
        return {}
