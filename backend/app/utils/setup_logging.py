"""Logging configuration using stdlib logging."""

import logging
import sys

from app.config import LogLevel


def setup_logging(level: LogLevel = LogLevel.INFO, logger_name: str | None = None) -> logging.Logger:
    """Set up logging configuration.

    Args:
        level: The application log level, converted to its stdlib numeric value.
        logger_name: The name of the logger to configure. If None, configures root logger.

    Returns:
        The configured logger.
    """
    numeric_level = logging.getLevelNamesMapping()[level.value]
    logger = logging.getLogger(logger_name)
    logger.setLevel(numeric_level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger
