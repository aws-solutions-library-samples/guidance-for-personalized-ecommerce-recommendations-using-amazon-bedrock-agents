"""Unit tests for the streaming response handler."""

import pytest

from cli.streaming import PerformanceMetrics, StreamingResponseHandler


class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics dataclass."""

    def test_defaults_to_none(self):
        metrics = PerformanceMetrics()
        assert metrics.time_to_first_token is None
        assert metrics.total_duration is None

    def test_accepts_values(self):
        metrics = PerformanceMetrics(time_to_first_token=1.5, total_duration=3.0)
        assert metrics.time_to_first_token == 1.5
        assert metrics.total_duration == 3.0


class TestStreamingResponseHandler:
    """Tests for the StreamingResponseHandler class."""

    def test_initial_state(self):
        handler = StreamingResponseHandler()
        assert handler.verbosity == 0
        assert handler.metrics.time_to_first_token is None
        assert handler.metrics.total_duration is None
        assert handler._spinner_running is False

    def test_initial_state_with_verbosity(self):
        handler = StreamingResponseHandler(verbosity=2)
        assert handler.verbosity == 2

    def test_start_spinner_sets_running_flag(self):
        handler = StreamingResponseHandler()
        handler._start_spinner()
        assert handler._spinner_running is True

    def test_stop_spinner_clears_running_flag(self):
        handler = StreamingResponseHandler()
        handler._start_spinner()
        assert handler._spinner_running is True
        handler._stop_spinner()
        assert handler._spinner_running is False

    def test_stop_spinner_noop_when_not_running(self):
        handler = StreamingResponseHandler()
        assert handler._spinner_running is False
        handler._stop_spinner()
        assert handler._spinner_running is False
