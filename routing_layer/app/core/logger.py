"""
Custom logging setup for the OpenFactory Routing Layer.

This module configures logging to support:
- Context-aware logger selection (CLI vs FastAPI/Uvicorn)
- Colored log levels (INFO, WARNING, etc.) for CLI
- Aligned logger names with fixed-width formatting for readability

Usage:
    - In CLI scripts: call `setup_logging()` once at startup.
    - To obtain a logger, use `get_logger(name)`.
"""

import logging
from routing_layer.app.config import settings


class ShortNameFormatter(logging.Formatter):
    """
    Custom formatter that:
      - Shortens module path (e.g., strips 'routing_layer.app.core.controller.')
      - Formats logger names in fixed-width aligned columns
      - Adds ANSI color codes for log levels (only in CLI)
    """

    LEVEL_COLORS = {
        'DEBUG': '\033[90m',        # Bright Black (gray)
        'INFO': '\033[32m',         # Green
        'WARNING': '\033[33m',      # Yellow
        'ERROR': '\033[31m',        # Red
        'CRITICAL': '\033[1;31m',   # Bold Red
    }
    RESET_COLOR = '\033[0m'
    NAME_WIDTH = 25                 # Fixed width for logger name field

    def __init__(self, fmt: str, use_colors: bool = True):
        """
        Initialize the formatter.

        Args:
            fmt (str): Format string for the log message.
            use_colors (bool): Whether to use ANSI colors for level names.
        """
        super().__init__(fmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with shortened and padded logger name,
        and optionally colorized level name.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: Formatted log message.
        """
        prefix = "routing_layer.app.core.controller."
        if record.name.startswith(prefix):
            record.name = record.name.replace(prefix, "")

        bracketed_name = f"[{record.name}]"
        bracketed_name = bracketed_name.ljust(self.NAME_WIDTH)
        record.name = bracketed_name

        if self.use_colors and record.levelname in self.LEVEL_COLORS:
            color = self.LEVEL_COLORS[record.levelname]
            record.levelname = f"{color}{record.levelname}{self.RESET_COLOR}"

        return super().format(record)


def setup_logging():
    """
    Configure the root logger with custom formatter.

    This should be called once at the beginning of any CLI script
    that wants clean, readable log output.
    """
    formatter = ShortNameFormatter('%(levelname)s  %(name)s   %(message)s', use_colors=True)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())


def get_logger(name: str = None) -> logging.Logger:
    """
    Return the appropriate logger instance depending on context.

    Args:
        name (str): The logger name, typically __name__ of the module.

    Returns:
        logging.Logger: Configured logger.
    """
    return logging.getLogger(name)
