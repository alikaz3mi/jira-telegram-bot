from __future__ import annotations

import json
from typing import Any, Dict, Optional

import google.generativeai as genai
from langchain_core.language_models.base import BaseLanguageModel
from langchain_google_genai import ChatGoogleGenerativeAI

from jira_telegram_bot.settings import GEMINI_SETTINGS
from jira_telegram_bot.use_cases.interfaces.llm_interface import LLMInterface


class GeminiGateway(LLMInterface):
    """
    Concrete adapter for calling Google's Gemini language models.
    """

    def __init__(self):
        """Initialize the Gemini gateway with API settings."""
        self.api_key = GEMINI_SETTINGS.token
        self.temperature = 0.2
        self.model_name = "gemini-2.0-flash"
        genai.configure(api_key=self.api_key)

    def get_llm(self) -> BaseLanguageModel:
        """
        Returns a ChatGoogleGenerativeAI client for use with LangChain.
        
        Returns:
            A ChatGoogleGenerativeAI language model instance.
        """
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            temperature=self.temperature,
            google_api_key=self.api_key,
            convert_system_message_to_human=True,
        )
    
    async def generate_text(
        self, prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using the Gemini API directly.
        
        Args:
            prompt: The prompt to send to the model.
            temperature: Controls randomness (lower is more deterministic).
            max_tokens: Maximum number of tokens to generate (called max_output_tokens in Gemini).
            
        Returns:
            Generated text as string.
        """
        generation_config = {
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            generation_config["max_output_tokens"] = max_tokens
        
        model = genai.GenerativeModel(self.model_name, generation_config=generation_config)
        response = model.generate_content(prompt)
        
        if hasattr(response, "text"):
            return response.text
        return ""

    async def generate_structured_output(
        self, prompt: str, output_schema: Dict[str, Any], temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Generate structured output according to the given schema.
        
        Since Gemini doesn't have native function calling like OpenAI,
        we use a workaround with JSON schema instructions.
        
        Args:
            prompt: The prompt to send to the model.
            output_schema: The schema that defines the expected output structure.
            temperature: Controls randomness (lower is more deterministic).
            
        Returns:
            Structured output as dictionary.
        """
        # Format a prompt that requests a structured response
        schema_prompt = (
            f"{prompt}\n\n"
            f"Respond with a JSON object that follows this schema:\n"
            f"{json.dumps(output_schema, indent=2)}\n\n"
            f"Ensure your response is valid JSON without any additional text."
        )
        
        model = genai.GenerativeModel(
            self.model_name, 
            generation_config={"temperature": temperature}
        )
        
        response = model.generate_content(schema_prompt)
        
        try:
            if hasattr(response, "text"):
                # Try to extract just the JSON part
                text = response.text
                # Find JSON boundaries
                start_idx = text.find('{')
                end_idx = text.rfind('}')
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = text[start_idx:end_idx+1]
                    return json.loads(json_str)
                
                # If we can't find JSON boundaries, try parsing the whole response
                return json.loads(text)
            
            return {}
        except json.JSONDecodeError:
            # Fallback to empty dict if JSON parsing fails
            return {}