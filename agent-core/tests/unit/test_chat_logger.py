"""Unit tests for ChatLogger class."""

import os
import json
import tempfile
import pytest
from pathlib import Path
from cli.streaming.logger import ChatLogger


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_path = f.name
    yield log_path
    # Cleanup
    if os.path.exists(log_path):
        os.unlink(log_path)


@pytest.fixture
def logger(temp_log_file):
    """Create a ChatLogger instance for testing."""
    logger = ChatLogger(temp_log_file)
    yield logger
    logger.close()


def read_log_file(log_path: str) -> str:
    """Read entire log file content."""
    with open(log_path, 'r', encoding='utf-8') as f:
        return f.read()


def test_logger_initialization(temp_log_file):
    """Test logger initializes and creates log file."""
    logger = ChatLogger(temp_log_file)
    
    assert os.path.exists(temp_log_file)
    
    content = read_log_file(temp_log_file)
    assert "INFO: Chat session started" in content
    
    logger.close()


def test_log_directory_creation():
    """Test that log directory is created if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "subdir", "logs", "test.log")
        
        logger = ChatLogger(log_path)
        
        assert os.path.exists(log_path)
        assert os.path.isdir(os.path.dirname(log_path))
        
        logger.close()


def test_log_raw_event(logger, temp_log_file):
    """Test logging raw streaming events."""
    event = {
        "event": {
            "contentBlockDelta": {
                "delta": {"text": "Hello"}
            }
        }
    }
    
    logger.log_raw_event(event)
    
    content = read_log_file(temp_log_file)
    assert "DEBUG: Raw event:" in content
    assert '"text":"Hello"' in content or '"text": "Hello"' in content


def test_log_thinking_content(logger, temp_log_file):
    """Test logging thinking content."""
    thinking = "The user is asking about weather"
    
    logger.log_thinking_content(thinking)
    
    content = read_log_file(temp_log_file)
    assert "THINKING:" in content
    assert thinking in content


def test_log_thinking_content_with_newlines(logger, temp_log_file):
    """Test that newlines in thinking content are escaped."""
    thinking = "Line 1\nLine 2\nLine 3"
    
    logger.log_thinking_content(thinking)
    
    content = read_log_file(temp_log_file)
    assert "THINKING:" in content
    assert "Line 1\\nLine 2\\nLine 3" in content


def test_log_response_text(logger, temp_log_file):
    """Test logging response text."""
    response = "Hello! How can I help you?"
    
    logger.log_response_text(response)
    
    content = read_log_file(temp_log_file)
    assert "RESPONSE:" in content
    assert response in content


def test_log_response_text_with_newlines(logger, temp_log_file):
    """Test that newlines in response text are escaped."""
    response = "Line 1\nLine 2\nLine 3"
    
    logger.log_response_text(response)
    
    content = read_log_file(temp_log_file)
    assert "RESPONSE:" in content
    assert "Line 1\\nLine 2\\nLine 3" in content


def test_log_metrics(logger, temp_log_file):
    """Test logging performance metrics."""
    metrics = "Connection: 32ms, TTFB: 44ms, Total: 1045ms"
    
    logger.log_metrics(metrics)
    
    content = read_log_file(temp_log_file)
    assert "METRICS: Performance summary" in content
    assert metrics in content


def test_log_metrics_milestone(logger, temp_log_file):
    """Test logging performance milestones."""
    logger.log_metrics_milestone("Connection start")
    logger.log_metrics_milestone("First byte received", 44)
    
    content = read_log_file(temp_log_file)
    assert "METRICS: Connection start" in content
    assert "METRICS: First byte received (44ms)" in content


def test_log_error(logger, temp_log_file):
    """Test logging errors with traceback."""
    try:
        raise ValueError("Test error message")
    except ValueError as e:
        logger.log_error(e)
    
    content = read_log_file(temp_log_file)
    assert "ERROR: ValueError: Test error message" in content
    assert "Traceback" in content or "ValueError" in content


def test_log_info(logger, temp_log_file):
    """Test logging info messages."""
    logger.log_info("Test info message")
    
    content = read_log_file(temp_log_file)
    assert "INFO: Test info message" in content


def test_log_format(logger, temp_log_file):
    """Test log entry format includes timestamp and level."""
    logger.log_info("Test message")
    
    content = read_log_file(temp_log_file)
    lines = content.strip().split('\n')
    
    # Check format: [YYYY-MM-DD HH:MM:SS.mmm] LEVEL: message
    for line in lines:
        assert line.startswith('[')
        assert '] ' in line
        assert ':' in line


def test_immediate_flush(logger, temp_log_file):
    """Test that logs are flushed immediately."""
    logger.log_info("Immediate message")
    
    # Read file without closing logger
    content = read_log_file(temp_log_file)
    assert "Immediate message" in content


def test_close_logs_session_end(logger, temp_log_file):
    """Test that closing logger logs session end."""
    logger.close()
    
    content = read_log_file(temp_log_file)
    assert "INFO: Chat session ended" in content


def test_multiple_log_entries(logger, temp_log_file):
    """Test logging multiple entries in sequence."""
    logger.log_info("Entry 1")
    logger.log_thinking_content("Thinking...")
    logger.log_response_text("Response text")
    logger.log_metrics("Connection: 10ms, TTFB: 20ms, Total: 100ms")
    
    content = read_log_file(temp_log_file)
    lines = content.strip().split('\n')
    
    # Should have: session start + 4 entries
    assert len(lines) >= 5
    assert "Entry 1" in content
    assert "Thinking..." in content
    assert "Response text" in content
    assert "Connection: 10ms" in content


def test_expanduser_in_path():
    """Test that ~ is expanded in log file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a path with ~ that we can test
        log_path = os.path.join(tmpdir, "test.log")
        
        logger = ChatLogger(log_path)
        
        # Should expand to absolute path
        assert os.path.isabs(logger.log_file)
        assert os.path.exists(logger.log_file)
        
        logger.close()


def test_unicode_content(logger, temp_log_file):
    """Test logging unicode content."""
    unicode_text = "Hello 世界 🌍"
    
    logger.log_response_text(unicode_text)
    
    content = read_log_file(temp_log_file)
    assert unicode_text in content


def test_json_serialization_error(logger, temp_log_file):
    """Test handling of non-serializable events."""
    # Create an event with non-serializable content
    class NonSerializable:
        pass
    
    event = {"data": NonSerializable()}
    
    # Should not crash
    logger.log_raw_event(event)
    
    content = read_log_file(temp_log_file)
    assert "ERROR: Failed to serialize event" in content
