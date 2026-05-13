"""Tests for logging utilities."""

import logging

import pytest

from ai_launcher.utils.logging import get_logger, setup_logging


def test_setup_logging_default():
    """Test default logging setup."""
    logger = setup_logging()

    assert logger.name == "ai_launcher"
    assert logger.level == logging.INFO
    assert len(logger.handlers) > 0


def test_setup_logging_with_level():
    """Test logging setup with custom level."""
    logger = setup_logging(level="DEBUG")

    assert logger.level == logging.DEBUG


def test_setup_logging_verbose(tmp_path):
    """Test logging setup with verbose mode."""
    log_file = tmp_path / "test.log"
    logger = setup_logging(level="DEBUG", log_file=log_file, verbose=True)

    # Should have console and file handlers in verbose mode
    assert len(logger.handlers) >= 2
    assert log_file.exists()


def test_setup_logging_with_file(tmp_path):
    """Test logging setup with log file."""
    log_file = tmp_path / "test.log"
    logger = setup_logging(log_file=log_file, verbose=True)

    # Write a log message
    logger.info("Test message")

    # Check file was created and contains message
    assert log_file.exists()
    content = log_file.read_text()
    assert "Test message" in content


def test_get_logger():
    """Test getting logger instance."""
    logger1 = get_logger()
    logger2 = get_logger()

    # Should return same logger instance
    assert logger1 is logger2
    assert logger1.name == "ai_launcher"


@pytest.mark.parametrize(
    "level_name",
    ["DEBUG", "INFO", "WARNING", "ERROR"],
    ids=["debug", "info", "warning", "error"],
)
def test_logging_levels(level_name):
    """Test that each logging level can be set correctly."""
    logger = setup_logging(level=level_name)
    expected_level = getattr(logging, level_name)
    assert logger.level == expected_level


def test_invalid_log_level():
    """Test handling of invalid log level."""
    # Should default to INFO for invalid level
    logger = setup_logging(level="INVALID")
    assert logger.level == logging.INFO
