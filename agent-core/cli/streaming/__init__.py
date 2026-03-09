"""
Streaming response processing module for CLI chat command.

This module provides modular components for handling streaming responses from
AWS Bedrock AgentCore API, including:

- SSE (Server-Sent Events) parsing
- Thinking tag filtering
- Terminal display with verbosity control
- File logging for debugging
- Performance metrics tracking
- Animated spinner for thinking indicator

The main entry point is StreamingResponseHandler which orchestrates all components.

Example usage:
    from cli.streaming import StreamingResponseHandler
    
    handler = StreamingResponseHandler(verbosity=0, log_file="chat.log")
    handler.process_stream(streaming_body)
"""

# Import all public classes for easy access
# These will be implemented in subsequent tasks
__all__ = [
    'StreamingResponseHandler',
    'SSEParser',
    'ThinkingTagFilter',
    'TerminalDisplay',
    'SpinnerAnimation',
    'ChatLogger',
    'PerformanceMetrics',
]

# Import all implemented classes
from .handler import StreamingResponseHandler
from .parser import SSEParser
from .filter import ThinkingTagFilter
from .display import TerminalDisplay, SpinnerAnimation
from .logger import ChatLogger
from .metrics import PerformanceMetrics
