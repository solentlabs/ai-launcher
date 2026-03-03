"""Tests for humanize utility functions."""

from datetime import datetime, timedelta

import pytest

from ai_launcher.utils.humanize import format_time_ago, humanize_count, humanize_size

# ============================================================================
# format_time_ago() tests
# ============================================================================


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(seconds=30), "just now"),
        (timedelta(seconds=59), "just now"),
        (timedelta(seconds=60), "1 minute ago"),
        (timedelta(minutes=1), "1 minute ago"),
        (timedelta(minutes=45), "45 minutes ago"),
        (timedelta(hours=1), "1 hour ago"),
        (timedelta(hours=5), "5 hours ago"),
        (timedelta(days=1), "1 day ago"),
        (timedelta(days=3), "3 days ago"),
        (timedelta(weeks=1), "1 week ago"),
        (timedelta(weeks=4), "4 weeks ago"),
    ],
    ids=[
        "30s_just_now",
        "59s_boundary_just_now",
        "60s_boundary_1_minute",
        "1_minute",
        "45_minutes",
        "1_hour",
        "5_hours",
        "1_day",
        "3_days",
        "1_week",
        "4_weeks",
    ],
)
def test_format_time_ago(delta, expected):
    """Test format_time_ago with various time deltas."""
    result = format_time_ago(datetime.now() - delta)
    assert result == expected


# ============================================================================
# humanize_size() tests
# ============================================================================


@pytest.mark.parametrize(
    "bytes_val,expected",
    [
        (0, "0 B"),
        (500, "500 B"),
        (1024, "1 KB"),
        (1536, "1.5 KB"),
        (1024 * 1024, "1 MB"),
        (int(2.5 * 1024 * 1024), "2.5 MB"),
        (1024 * 1024 * 1024, "1 GB"),
        (1024**4, "1 TB"),
        (5 * 1024**4, "5 TB"),
    ],
    ids=[
        "zero",
        "bytes",
        "1_kb",
        "fractional_kb",
        "1_mb",
        "fractional_mb",
        "1_gb",
        "1_tb",
        "5_tb",
    ],
)
def test_humanize_size(bytes_val, expected):
    """Test humanize_size with various byte values."""
    assert humanize_size(bytes_val) == expected


def test_humanize_size_strips_trailing_zero():
    """Test that .0 is stripped from whole numbers."""
    result = humanize_size(1024)
    assert result == "1 KB"
    assert ".0" not in result


def test_humanize_size_keeps_decimal():
    """Test that non-.0 decimals are kept."""
    result = humanize_size(1536)
    assert result == "1.5 KB"


# ============================================================================
# humanize_count() tests
# ============================================================================


@pytest.mark.parametrize(
    "count,singular,plural,expected",
    [
        (0, "file", "", "0 files"),
        (1, "file", "", "1 file"),
        (5, "file", "", "5 files"),
        (2, "item", "", "2 items"),
        (1, "directory", "directories", "1 directory"),
        (3, "directory", "directories", "3 directories"),
    ],
    ids=[
        "zero_plural",
        "singular",
        "many_plural",
        "default_s_plural",
        "custom_plural_singular",
        "custom_plural_many",
    ],
)
def test_humanize_count(count, singular, plural, expected):
    """Test humanize_count with various counts and plural forms."""
    assert humanize_count(count, singular, plural) == expected
