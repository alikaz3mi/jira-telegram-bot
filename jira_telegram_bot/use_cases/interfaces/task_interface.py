from __future__ import annotations

from abc import ABC
from abc import abstractmethod


class TaskInterface(ABC):
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def start(self, *args, **kwargs):
        pass

    @abstractmethod
    def finalize_task(self):
        pass
