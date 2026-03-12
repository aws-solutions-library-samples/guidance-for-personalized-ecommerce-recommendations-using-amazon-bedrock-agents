"""Unit tests for time parsing and log formatting utilities."""

import json
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

import click

from cli.sales_agent_cli import (
    parse_time_expression,
    _detect_severity,
    _format_log_message,
)


class TestParseTimeExpression:
    """Tests for parse_time_expression."""

    def test_iso8601_utc_timestamp(self):
        result = parse_time_expression("2025-01-15T10:30:00Z")
        expected_dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        expected_ms = int(expected_dt.timestamp() * 1000)
        assert result == expected_ms

    def test_iso8601_with_offset(self):
        result = parse_time_expression("2025-01-15T10:30:00+00:00")
        expected_dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        expected_ms = int(expected_dt.timestamp() * 1000)
        assert result == expected_ms

    def test_relative_hours_ago(self):
        before = datetime.now(timezone.utc) - timedelta(hours=1, seconds=2)
        result = parse_time_expression("1h ago")
        after = datetime.now(timezone.utc) - timedelta(hours=1)
        # Result should be between before and after (within tolerance)
        before_ms = int(before.timestamp() * 1000)
        after_ms = int(after.timestamp() * 1000)
        assert before_ms <= result <= after_ms

    def test_relative_minutes_ago(self):
        before = datetime.now(timezone.utc) - timedelta(minutes=30, seconds=2)
        result = parse_time_expression("30m ago")
        after = datetime.now(timezone.utc) - timedelta(minutes=30)
        before_ms = int(before.timestamp() * 1000)
        after_ms = int(after.timestamp() * 1000)
        assert before_ms <= result <= after_ms

    def test_invalid_expression_raises_click_exception(self):
        with pytest.raises(click.ClickException, match="Invalid time expression"):
            parse_time_expression("not-a-time")

    def test_empty_string_raises_click_exception(self):
        with pytest.raises(click.ClickException, match="Invalid time expression"):
            parse_time_expression("  ")


class TestDetectSeverity:
    """Tests for _detect_severity."""

    def test_error_level(self):
        assert _detect_severity("ERROR: something failed") == "ERROR"

    def test_warn_level(self):
        assert _detect_severity("WARN: something suspicious") == "WARN"

    def test_warning_level(self):
        # "WARNING" contains "WARN" which matches first in the detection order
        assert _detect_severity("WARNING: check this") == "WARN"

    def test_info_level(self):
        assert _detect_severity("INFO: all good") == "INFO"

    def test_debug_level(self):
        assert _detect_severity("DEBUG: trace details") == "DEBUG"

    def test_unknown_defaults_to_info(self):
        assert _detect_severity("just a plain message") == "INFO"

    def test_case_insensitive(self):
        assert _detect_severity("error in lowercase") == "ERROR"


class TestFormatLogMessage:
    """Tests for _format_log_message."""

    def test_pretty_prints_json(self):
        raw = '{"key": "value", "num": 42}'
        result = _format_log_message(raw)
        parsed = json.loads(result)
        assert parsed == {"key": "value", "num": 42}
        assert "\n" in result  # pretty-printed

    def test_returns_plain_text_unchanged(self):
        msg = "This is not JSON"
        assert _format_log_message(msg) == msg

    def test_nested_json_pretty_printed(self):
        raw = '{"outer": {"inner": "value"}}'
        result = _format_log_message(raw)
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == "value"
