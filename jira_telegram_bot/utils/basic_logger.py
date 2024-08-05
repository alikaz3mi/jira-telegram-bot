import os
import sys
import logging
from loguru import logger


def get_splitter_format():
    return "\n" + "-" * 100


class ColoredFormatter(logging.Formatter):
    green = "\u001b[32m"
    grey = "\u001b[36m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    splitter = get_splitter_format()

    def __init__(self, *args, **kwargs):
        super(ColoredFormatter, self).__init__(*args, **kwargs)
        self._level_color_format = {
            logging.NOTSET: self.reset + "{}" + self.reset,
            logging.DEBUG: self.grey + "{}" + self.reset,
            logging.INFO: self.blue + "{}" + self.reset,
            logging.WARNING: self.yellow + "{}" + self.reset,
            logging.ERROR: self.red + "{}" + self.reset,
            logging.CRITICAL: self.bold_red + "{}" + self.reset,
        }
        self._message_color_format = self.green + "{}" + self.reset

    def format(self, record: logging.LogRecord) -> str:
        # replace the level name with related level color
        record.levelname = self._level_color_format.get(record.levelno).format(
            record.levelname
        )
        record.msg = self._message_color_format.format(record.msg)
        return super(ColoredFormatter, self).format(record) + self.splitter


def simple_logger(
    name, stream_level=logging.DEBUG, file_level=logging.DEBUG, filename: str = None
):
    if "--stream_level" in sys.argv:
        idx = sys.argv.index("--stream_level")
        try:
            stream_level = eval(sys.argv[idx + 1])
        except Exception as e:
            raise e
    if "--stream_level" in os.environ:
        idx = eval(os.environ["stream_level"])
    logger = logging.getLogger(name)
    file_format = "%(levelname)s-%(asctime)s-FILENAME:%(filename)s-MODULE:%(module)s-%(lineno)d-FUNC:%(funcName)s-THREAD:%(threadName)s :: %(message)s"
    console_format = "%(levelname)s-%(asctime)s-FILENAME:%(filename)s-MODULE:%(module)s-%(lineno)d-FUNC:%(funcName)s-THREAD:%(threadName)s :: %(message)s"
    file_formatter = logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_formatter = ColoredFormatter(console_format, datefmt="%Y-%m-%d %H:%M:%S")
    if filename is not None:
        file_handler = logging.FileHandler(filename=filename)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)

        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(stream_level)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG)

    logger.propagate = False
    return logger


def loguru_logger(
    name,
    stream_level="DEBUG",
    file_level="DEBUG",
    filename: str = None,
    enqueue: bool = True,
):
    # Remove default handlers to avoid duplicate logs
    logger.remove()

    # Determine stream level from command line arguments or environment variables
    if "--stream_level" in sys.argv:
        idx = sys.argv.index("--stream_level")
        try:
            stream_level = sys.argv[idx + 1]
        except Exception as e:
            raise e
    if "--stream_level" in os.environ:
        stream_level = os.environ["stream_level"]

    # Set formatter for console output
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level}</level> | "
        "FILENAME: <cyan>{file}</cyan> - "
        "MODULE: <cyan>{module}</cyan> - "
        "FUNC: <cyan>{function}</cyan> - "
        "LINE: <cyan>{line}</cyan> - "
        "THREAD: <cyan>{thread.name}</cyan> :: "
        "<level>{message}</level>"
    )

    # Add console handler
    logger.add(sys.stdout, level=stream_level, format=console_format, colorize=True)

    if filename is not None:
        # Set file format
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level} | "
            "FILENAME: {file} - "
            "MODULE: {module} - "
            "FUNC: {function} - "
            "LINE: {line} - "
            "THREAD: {thread.name} :: "
            "{message}\n" + "-" * 100
        )

        # Add file handler with rotation and asynchronous logging
        logger.add(filename, level=file_level, format=file_format, enqueue=enqueue)

    logger.info(
        f"Logger '{name}' initialized with stream level '{stream_level}' and file level '{file_level}'"
    )

    return logger


__all__ = ("simple_logger", "loguru_logger")
