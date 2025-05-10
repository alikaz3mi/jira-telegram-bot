from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from langchain_core.language_models.base import BaseLanguageModel


class OpenAIGatewayInterface(ABC):
    @abstractmethod
    def get_llm(self) -> BaseLanguageModel:
        """Return a language model client or wrapper compatible with LangChain.
        
        Returns:
            A language model client compatible with LangChain's BaseLanguageModel.
        """
        pass
