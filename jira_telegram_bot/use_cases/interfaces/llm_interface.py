from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.language_models.base import BaseLanguageModel


class LLMInterface(ABC):
    """Interface for Language Model providers (OpenAI, Google, etc.)."""
    
    @abstractmethod
    def get_llm(self) -> BaseLanguageModel:
        """Return a language model instance compatible with LangChain's BaseLanguageModel."""
        pass
    
    @abstractmethod
    async def generate_text(
        self, prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None
    ) -> str:
        """Generate text using the language model.
        
        Args:
            prompt: The prompt to send to the model
            temperature: Controls randomness (lower is more deterministic)
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text as string
        """
        pass
    
    @abstractmethod
    async def generate_structured_output(
        self, prompt: str, output_schema: Dict[str, Any], temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Generate structured output according to the given schema.
        
        Args:
            prompt: The prompt to send to the model
            output_schema: The schema that defines the expected output structure
            temperature: Controls randomness (lower is more deterministic)
            
        Returns:
            Structured output as dictionary
        """
        pass