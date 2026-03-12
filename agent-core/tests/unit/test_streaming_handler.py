"""Integration tests for StreamingResponseHandler."""

import io
import json
import tempfile
import pytest
from unittest.mock import Mock, MagicMock
from cli.streaming.handler import StreamingResponseHandler
from cli.streaming.metrics import PerformanceMetrics


class MockStreamingBody:
    """Mock StreamingBody for testing."""
    
    def __init__(self, lines):
        """Initialize with list of lines to stream."""
        self.lines = lines
    
    def iter_lines(self):
        """Iterate over lines."""
        for line in self.lines:
            if isinstance(line, str):
                yield line.encode('utf-8')
            else:
                yield line


def create_sse_event(text: str) -> bytes:
    """Create an SSE event with text content."""
    event = {
        "event": {
            "contentBlockDelta": {
                "delta": {"text": text}
            }
        }
    }
    return f"data: {json.dumps(event)}".encode('utf-8')


@pytest.fixture
def temp_log_file():
    """Create a temporary log file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        return f.name


@pytest.fixture
def metrics():
    """Create a PerformanceMetrics instance."""
    metrics = PerformanceMetrics()
    metrics.mark_connection_start()
    metrics.mark_connection_established()
    return metrics


def test_handler_initialization(temp_log_file, metrics):
    """Test handler initializes all components."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    assert handler.parser is not None
    assert handler.filter is not None
    assert handler.display is not None
    assert handler.logger is not None
    assert handler.metrics is not None
    assert handler.verbosity == 0
    
    # Clean up
    handler.logger.close()


def test_process_simple_response(temp_log_file, metrics, capsys):
    """Test processing a simple response without thinking tags."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with simple response
    lines = [
        create_sse_event("Hello"),
        create_sse_event(" world"),
        create_sse_event("!")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check output
    captured = capsys.readouterr()
    assert "Hello world!" in captured.out
    assert "Agent[" in captured.out


def test_process_response_with_thinking(temp_log_file, metrics, capsys):
    """Test processing response with thinking tags."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with thinking tags
    lines = [
        create_sse_event("<thinking>"),
        create_sse_event("Internal thoughts"),
        create_sse_event("</thinking>"),
        create_sse_event("Hello world")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check output - thinking should be hidden
    captured = capsys.readouterr()
    assert "Internal thoughts" not in captured.out
    assert "Hello world" in captured.out
    assert "Thinking:" in captured.out  # Spinner shown


def test_process_response_verbose_mode(temp_log_file, metrics, capsys):
    """Test processing response in verbose mode shows thinking content."""
    handler = StreamingResponseHandler(
        verbosity=1,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with thinking tags
    lines = [
        create_sse_event("<thinking>"),
        create_sse_event("Internal thoughts"),
        create_sse_event("</thinking>"),
        create_sse_event("Hello world")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check output - thinking should be visible in verbose mode
    captured = capsys.readouterr()
    assert "Internal thoughts" in captured.out
    assert "Hello world" in captured.out
    assert "[Metrics]" in captured.out  # Metrics shown in verbose mode


def test_process_response_debug_mode(temp_log_file, metrics, capsys):
    """Test processing response in debug mode shows raw events."""
    handler = StreamingResponseHandler(
        verbosity=2,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body
    lines = [
        create_sse_event("Hello")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check output - raw events should be visible
    captured = capsys.readouterr()
    assert "[RAW EVENT]" in captured.out


def test_marks_first_byte(temp_log_file, metrics):
    """Test that first byte is marked when first chunk arrives."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Initially no first byte
    assert metrics.first_byte_received is None
    
    # Create mock streaming body
    lines = [create_sse_event("Hello")]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # First byte should be marked
    assert metrics.first_byte_received is not None


def test_marks_stream_complete(temp_log_file, metrics):
    """Test that stream complete is marked at end."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Initially no stream complete
    assert metrics.stream_complete is None
    
    # Create mock streaming body
    lines = [create_sse_event("Hello")]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Stream complete should be marked
    assert metrics.stream_complete is not None


def test_logs_metrics_summary(temp_log_file, metrics):
    """Test that metrics summary is logged."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body
    lines = [create_sse_event("Hello")]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check log file contains metrics
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    assert "METRICS: Performance summary" in log_content


def test_logs_response_text(temp_log_file, metrics):
    """Test that response text is logged."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body
    lines = [create_sse_event("Hello world")]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check log file contains response
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    assert "RESPONSE: Hello world" in log_content


def test_logs_thinking_content(temp_log_file, metrics):
    """Test that thinking content is logged."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with thinking
    lines = [
        create_sse_event("<thinking>Internal</thinking>"),
        create_sse_event("Hello")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check log file contains thinking
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    assert "THINKING: Internal" in log_content


def test_handles_empty_lines(temp_log_file, metrics):
    """Test that empty lines are handled gracefully."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with empty lines
    lines = [
        b'',
        create_sse_event("Hello"),
        b'',
        create_sse_event(" world")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Should not crash
    handler.process_stream(streaming_body)


def test_handles_malformed_json(temp_log_file, metrics):
    """Test that malformed JSON is handled gracefully."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with malformed JSON
    lines = [
        b'data: {invalid json}',
        create_sse_event("Hello")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Should not crash
    handler.process_stream(streaming_body)


def test_elapsed_time_calculation(temp_log_file, metrics, capsys):
    """Test that elapsed time is calculated and displayed."""
    handler = StreamingResponseHandler(
        verbosity=0,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body
    lines = [create_sse_event("Hello")]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check that elapsed time is shown
    captured = capsys.readouterr()
    assert "Agent[" in captured.out
    assert "s]:" in captured.out  # Format: Agent[X.Xs]:


def test_multiple_thinking_blocks(temp_log_file, metrics, capsys):
    """Test handling multiple thinking blocks in one response."""
    handler = StreamingResponseHandler(
        verbosity=1,
        log_file=temp_log_file,
        metrics=metrics
    )
    
    # Create mock streaming body with multiple thinking blocks
    lines = [
        create_sse_event("<thinking>First</thinking>"),
        create_sse_event("Hello"),
        create_sse_event("<thinking>Second</thinking>"),
        create_sse_event(" world")
    ]
    streaming_body = MockStreamingBody(lines)
    
    # Process stream
    handler.process_stream(streaming_body)
    
    # Check log file has both thinking blocks
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    assert "THINKING: First" in log_content
    assert "THINKING: Second" in log_content
    
    # Check output has both (in verbose mode)
    captured = capsys.readouterr()
    assert "First" in captured.out
    assert "Second" in captured.out
