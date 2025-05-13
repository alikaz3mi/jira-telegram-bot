from __future__ import annotations

__version__ = "2.30.28"
__name__ = "jira_telegram_bot"

import os
from pathlib import Path

from jira_telegram_bot.utils.basic_logger import loguru_logger

DEFAULT_PATH = Path(os.path.realpath(__file__)).parents[1]


from chromatrace import LoggingConfig, LoggingSettings


DEFAULT_PATH = Path(os.path.realpath(__file__)).parents[1]
CACHE_DIR = Path.home()


logging_config = LoggingConfig(
    settings=LoggingSettings(
        application_level="DEBUG",
        enable_tracing=True,
        ignore_nan_trace=True,
        log_level="DEBUG",
        file_path="logs.log",
        enable_file_logging=True,
        max_bytes=10 * 1024 * 1024,
        backup_count=50,
    )
)
LOGGER = logging_config.get_logger(__name__)


__all__ = ["__version__", "__name__", "loguru_logger", "DEFAULT_PATH"]
