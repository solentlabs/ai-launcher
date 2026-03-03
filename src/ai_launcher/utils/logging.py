"""Logging configuration for ai-launcher."""

import logging
import sys
from pathlib import Path
from typing import Optional

from platformdirs import user_log_path


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure logging for ai-launcher.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
        verbose: If True, set level to DEBUG

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("ai_launcher")

    # Set level
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if log file specified or in debug mode)
    if log_file or verbose:
        if log_file is None:
            log_dir = user_log_path("ai-launcher")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "ai-launcher.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        if verbose:
            logger.info(f"Logging to file: {log_file}")

    # Don't propagate to root logger
    logger.propagate = False

    return logger


def get_logger(name: str = "ai_launcher") -> logging.Logger:
    """Get logger instance.

    Args:
        name: Logger name (default: ai_launcher)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
