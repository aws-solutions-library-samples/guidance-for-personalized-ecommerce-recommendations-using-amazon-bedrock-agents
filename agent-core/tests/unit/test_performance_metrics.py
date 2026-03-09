"""Unit tests for PerformanceMetrics class."""

import time
import pytest
from cli.streaming.metrics import PerformanceMetrics


def test_initial_state():
    """Test that metrics start with no timestamps."""
    metrics = PerformanceMetrics()
    
    assert metrics.connection_start is None
    assert metrics.connection_established is None
    assert metrics.first_byte_received is None
    assert metrics.stream_complete is None


def test_mark_connection_start():
    """Test marking connection start time."""
    metrics = PerformanceMetrics()
    
    before = time.perf_counter()
    metrics.mark_connection_start()
    after = time.perf_counter()
    
    assert metrics.connection_start is not None
    assert before <= metrics.connection_start <= after


def test_mark_connection_established():
    """Test marking connection established time."""
    metrics = PerformanceMetrics()
    
    before = time.perf_counter()
    metrics.mark_connection_established()
    after = time.perf_counter()
    
    assert metrics.connection_established is not None
    assert before <= metrics.connection_established <= after


def test_mark_first_byte():
    """Test marking first byte received time."""
    metrics = PerformanceMetrics()
    
    before = time.perf_counter()
    metrics.mark_first_byte()
    after = time.perf_counter()
    
    assert metrics.first_byte_received is not None
    assert before <= metrics.first_byte_received <= after


def test_mark_first_byte_only_once():
    """Test that first byte is only marked once."""
    metrics = PerformanceMetrics()
    
    metrics.mark_first_byte()
    first_timestamp = metrics.first_byte_received
    
    time.sleep(0.01)  # Small delay
    metrics.mark_first_byte()  # Try to mark again
    
    assert metrics.first_byte_received == first_timestamp


def test_mark_stream_complete():
    """Test marking stream complete time."""
    metrics = PerformanceMetrics()
    
    before = time.perf_counter()
    metrics.mark_stream_complete()
    after = time.perf_counter()
    
    assert metrics.stream_complete is not None
    assert before <= metrics.stream_complete <= after


def test_get_connection_time():
    """Test calculating connection time."""
    metrics = PerformanceMetrics()
    
    metrics.mark_connection_start()
    time.sleep(0.01)  # Simulate connection delay
    metrics.mark_connection_established()
    
    conn_time = metrics.get_connection_time()
    
    assert conn_time is not None
    assert conn_time >= 0.01  # At least 10ms
    assert conn_time < 0.1  # Less than 100ms (reasonable upper bound)


def test_get_connection_time_missing_timestamps():
    """Test connection time returns None when timestamps missing."""
    metrics = PerformanceMetrics()
    
    # No timestamps
    assert metrics.get_connection_time() is None
    
    # Only start
    metrics.mark_connection_start()
    assert metrics.get_connection_time() is None
    
    # Only established
    metrics = PerformanceMetrics()
    metrics.mark_connection_established()
    assert metrics.get_connection_time() is None


def test_get_ttfb():
    """Test calculating time to first byte."""
    metrics = PerformanceMetrics()
    
    metrics.mark_connection_start()
    time.sleep(0.01)  # Simulate delay
    metrics.mark_first_byte()
    
    ttfb = metrics.get_ttfb()
    
    assert ttfb is not None
    assert ttfb >= 0.01  # At least 10ms
    assert ttfb < 0.1  # Less than 100ms


def test_get_ttfb_missing_timestamps():
    """Test TTFB returns None when timestamps missing."""
    metrics = PerformanceMetrics()
    
    # No timestamps
    assert metrics.get_ttfb() is None
    
    # Only start
    metrics.mark_connection_start()
    assert metrics.get_ttfb() is None
    
    # Only first byte
    metrics = PerformanceMetrics()
    metrics.mark_first_byte()
    assert metrics.get_ttfb() is None


def test_get_total_time():
    """Test calculating total response time."""
    metrics = PerformanceMetrics()
    
    metrics.mark_connection_start()
    time.sleep(0.01)  # Simulate processing
    metrics.mark_stream_complete()
    
    total_time = metrics.get_total_time()
    
    assert total_time is not None
    assert total_time >= 0.01  # At least 10ms
    assert total_time < 0.1  # Less than 100ms


def test_get_total_time_missing_timestamps():
    """Test total time returns None when timestamps missing."""
    metrics = PerformanceMetrics()
    
    # No timestamps
    assert metrics.get_total_time() is None
    
    # Only start
    metrics.mark_connection_start()
    assert metrics.get_total_time() is None
    
    # Only complete
    metrics = PerformanceMetrics()
    metrics.mark_stream_complete()
    assert metrics.get_total_time() is None


def test_format_summary_complete():
    """Test formatting complete metrics summary."""
    metrics = PerformanceMetrics()
    
    metrics.mark_connection_start()
    time.sleep(0.01)
    metrics.mark_connection_established()
    time.sleep(0.01)
    metrics.mark_first_byte()
    time.sleep(0.01)
    metrics.mark_stream_complete()
    
    summary = metrics.format_summary()
    
    assert "Connection:" in summary
    assert "TTFB:" in summary
    assert "Total:" in summary
    assert "ms" in summary


def test_format_summary_missing_metrics():
    """Test formatting when metrics not available."""
    metrics = PerformanceMetrics()
    
    summary = metrics.format_summary()
    
    assert summary == "Performance metrics not available"


def test_format_summary_format():
    """Test that summary format matches expected pattern."""
    metrics = PerformanceMetrics()
    
    # Set up known timing
    metrics.mark_connection_start()
    time.sleep(0.032)  # ~32ms
    metrics.mark_connection_established()
    time.sleep(0.012)  # ~12ms more (44ms total)
    metrics.mark_first_byte()
    time.sleep(0.001)  # ~1ms more
    metrics.mark_stream_complete()
    
    summary = metrics.format_summary()
    
    # Should match pattern: "Connection: Xms, TTFB: Yms, Total: Zms"
    parts = summary.split(", ")
    assert len(parts) == 3
    assert parts[0].startswith("Connection: ")
    assert parts[0].endswith("ms")
    assert parts[1].startswith("TTFB: ")
    assert parts[1].endswith("ms")
    assert parts[2].startswith("Total: ")
    assert parts[2].endswith("ms")


def test_realistic_timing_sequence():
    """Test realistic timing sequence with all milestones."""
    metrics = PerformanceMetrics()
    
    # Simulate realistic API call sequence
    metrics.mark_connection_start()
    time.sleep(0.03)  # Connection time
    metrics.mark_connection_established()
    time.sleep(0.01)  # Time to first byte
    metrics.mark_first_byte()
    time.sleep(0.05)  # Streaming time
    metrics.mark_stream_complete()
    
    # Verify all metrics available
    assert metrics.get_connection_time() is not None
    assert metrics.get_ttfb() is not None
    assert metrics.get_total_time() is not None
    
    # Verify timing relationships
    conn_time = metrics.get_connection_time()
    ttfb = metrics.get_ttfb()
    total_time = metrics.get_total_time()
    
    assert conn_time < ttfb  # Connection happens before first byte
    assert ttfb < total_time  # First byte happens before completion
    
    # Verify reasonable values (with tolerance for system variability)
    assert 0.025 < conn_time < 0.040  # ~30ms (with tolerance)
    assert 0.035 < ttfb < 0.050  # ~40ms (with tolerance)
    assert 0.085 < total_time < 0.105  # ~90ms (with tolerance)
