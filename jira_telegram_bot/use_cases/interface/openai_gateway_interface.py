from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from langchain_openai import ChatOpenAI


class OpenAIGatewayInterface(ABC):
    @abstractmethod
    def get_llm(self) -> ChatOpenAI:
        """Return a ChatOpenAI client or a similar LLM wrapper."""
        pass
