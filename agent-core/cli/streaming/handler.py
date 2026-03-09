"""Streaming response handler orchestrator.

This module provides the StreamingResponseHandler class which coordinates
all streaming response processing components (parser, filter, display, logger, metrics).
"""

import time
from typing import Any
from botocore.response import StreamingBody

from .parser import SSEParser
from .filter import ThinkingTagFilter
from .display import TerminalDisplay
from .logger import ChatLogger
from .metrics import PerformanceMetrics


class StreamingResponseHandler:
    """Orchestrator for streaming response processing.
    
    Coordinates data flow between components:
    - SSEParser: Parses SSE format and extracts text
    - ThinkingTagFilter: Filters thinking tags from text
    - TerminalDisplay: Shows output with verbosity control
    - ChatLogger: Logs all events to file
    - PerformanceMetrics: Tracks timing metrics
    
    Data flow:
        StreamingBody → Parser → Filter → Display
                                    ↓
                                 Logger
    """
    
    def __init__(self, verbosity: int, log_file: str, metrics: PerformanceMetrics):
        """Initialize handler with all components.
        
        Args:
            verbosity: Output verbosity level (0, 1, or 2)
            log_file: Path to log file
            metrics: PerformanceMetrics instance (already tracking connection)
        """
        self.parser = SSEParser()
        self.filter = ThinkingTagFilter()
        self.display = TerminalDisplay(verbosity)
        self.logger = ChatLogger(log_file)
        self.metrics = metrics
        self.verbosity = verbosity
        
        self.start_time = None
        self.first_chunk_received = False
    
    def process_stream(self, streaming_body: StreamingBody) -> None:
        """Process streaming response from AgentCore API.
        
        Reads the streaming body line by line, parses events, filters thinking
        tags, displays output, and logs everything for debugging.
        
        Args:
            streaming_body: StreamingBody from boto3 API response
        """
        self.start_time = time.time()
        
        try:
            # Process each line from the stream
            for line in streaming_body.iter_lines():
                if not line:
                    continue
                
                # Mark first byte received
                if not self.first_chunk_received:
                    self.metrics.mark_first_byte()
                    self.first_chunk_received = True
                
                # Parse SSE line to extract text
                text = self.parser.parse_line(line)
                
                # Log raw event if verbosity >= 2
                if self.verbosity >= 2:
                    try:
                        import json
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data:'):
                            json_str = line_str[5:].strip()
                            if json_str:
                                event = json.loads(json_str)
                                self.logger.log_raw_event(event)
                                self.display.show_raw_event(event)
                    except Exception:
                        pass  # Ignore parsing errors for raw event display
                
                # If no text extracted, continue to next line
                if text is None:
                    continue
                
                # Handle the text chunk
                self._handle_text_chunk(text)
            
            # Mark stream complete
            self.metrics.mark_stream_complete()
            
            # Finish response display
            self.display.finish_response()
            
            # Log and display performance metrics
            metrics_summary = self.metrics.format_summary()
            self.logger.log_metrics(metrics_summary)
            self.display.show_metrics(metrics_summary)
            
            # Log completion
            elapsed = time.time() - self.start_time
            self.logger.log_info(f"Response complete (elapsed: {elapsed:.3f}s)")
            
        except Exception as e:
            self.logger.log_error(e)
            raise
        finally:
            self.logger.close()
    
    def _handle_text_chunk(self, text: str) -> None:
        """Handle a single text chunk from the stream.
        
        Processes text through the filter, displays thinking indicator,
        shows response text, and logs everything.
        
        Args:
            text: Text chunk extracted from SSE event
        """
        # Process text through thinking tag filter
        displayable_text, thinking_content = self.filter.process_text(text)
        
        # If we have thinking content, log and display it
        if thinking_content:
            self.logger.log_thinking_content(thinking_content)
            self.display.show_thinking_content(thinking_content)
        
        # Show thinking indicator while in thinking mode
        if self.filter.state.value == "thinking":
            self.display.show_thinking()
        
        # If we have displayable text, show and log it
        if displayable_text:
            # Calculate elapsed time for agent label
            elapsed_time = None
            if self.start_time:
                elapsed_time = time.time() - self.start_time
            
            # Display agent response
            self.display.show_agent_response(displayable_text, elapsed_time)
            
            # Log response text
            self.logger.log_response_text(displayable_text)
