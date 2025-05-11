from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from jira_telegram_bot.use_cases.interfaces.task_interface import TaskInterface


class TaskHandlerInterface(ABC):
    @abstractmethod
    def __init__(self, task: TaskInterface):
        pass

    @abstractmethod
    def get_handler(self, *args, **kwargs):
        pass

    @abstractmethod
    def cancel(self, *args, **kwargs):
        pass
