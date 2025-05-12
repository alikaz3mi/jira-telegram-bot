from __future__ import annotations

from abc import ABC
from abc import abstractmethod


class LLMModelInterface(ABC):
    @abstractmethod
    def __getitem__(self, *args, **kwargs):
        """
        Get the model by name.
        """
        pass

    @abstractmethod
    def register(self, *args, **kwargs):
        """
        Register a new model.
        """
        pass
