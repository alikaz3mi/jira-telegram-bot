from __future__ import annotations

__version__ = "2.30.27"
__name__ = "jira_telegram_bot"

import os
from pathlib import Path

from jira_telegram_bot.utils.basic_logger import loguru_logger

DEFAULT_PATH = Path(os.path.realpath(__file__)).parents[1]


LOGGER = loguru_logger(__name__)


__all__ = ["__version__", "__name__", "loguru_logger", "DEFAULT_PATH"]
