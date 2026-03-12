"""File logging for streaming chat responses.

This module provides comprehensive logging of streaming events, thinking content,
response text, and performance metrics for debugging and analysis.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class ChatLogger:
    """File logger for chat streaming events and metrics.
    
    Logs all streaming events, thinking content, response text, and performance
    metrics to a timestamped log file for debugging and analysis.
    
    Log file location: ~/.sales-agent-cli/logs/chat-{timestamp}.log
    Log format: [TIMESTAMP] LEVEL: message
    """
    
    def __init__(self, log_file: str):
        """Initialize logger with specified log file path.
        
        Args:
            log_file: Path to log file (will be created if doesn't exist)
        """
        self.log_file = self._ensure_log_file(log_file)
        self.file_handle = open(self.log_file, 'a', encoding='utf-8')
        self._log("INFO", "Chat session started")
    
    def _ensure_log_file(self, log_file: str) -> str:
        """Ensure log directory exists and return full log file path.
        
        Args:
            log_file: Log file path (can be relative or absolute)
            
        Returns:
            Absolute path to log file
        """
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return str(log_path)
    
    def _log(self, level: str, message: str) -> None:
        """Write log entry with timestamp and level.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, METRICS, THINKING, RESPONSE)
            message: Log message
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            log_entry = f"[{timestamp}] {level}: {message}\n"
            self.file_handle.write(log_entry)
            self.file_handle.flush()  # Immediate flush for real-time logging
        except Exception as e:
            # Fail silently to avoid disrupting chat flow
            print(f"Warning: Failed to write to log file: {e}", flush=True)
    
    def log_raw_event(self, event: Dict[str, Any]) -> None:
        """Log raw streaming event.
        
        Args:
            event: Raw event dictionary from streaming response
        """
        try:
            event_json = json.dumps(event, separators=(',', ':'))
            self._log("DEBUG", f"Raw event: {event_json}")
        except Exception as e:
            self._log("ERROR", f"Failed to serialize event: {e}")
    
    def log_thinking_content(self, content: str) -> None:
        """Log extracted thinking content.
        
        Args:
            content: Thinking content extracted from <thinking> tags
        """
        # Escape newlines for single-line log entry
        escaped_content = content.replace('\n', '\\n')
        self._log("THINKING", escaped_content)
    
    def log_response_text(self, text: str) -> None:
        """Log displayable response text.
        
        Args:
            text: Response text to be displayed to user
        """
        # Escape newlines for single-line log entry
        escaped_text = text.replace('\n', '\\n')
        self._log("RESPONSE", escaped_text)
    
    def log_metrics(self, metrics_summary: str) -> None:
        """Log performance metrics summary.
        
        Args:
            metrics_summary: Formatted metrics string (e.g., "Connection: 32ms, TTFB: 44ms, Total: 1045ms")
        """
        self._log("METRICS", f"Performance summary - {metrics_summary}")
    
    def log_metrics_milestone(self, milestone: str, elapsed_ms: Optional[int] = None) -> None:
        """Log a performance milestone.
        
        Args:
            milestone: Milestone name (e.g., "Connection start", "First byte received")
            elapsed_ms: Optional elapsed time in milliseconds from start
        """
        if elapsed_ms is not None:
            self._log("METRICS", f"{milestone} ({elapsed_ms}ms)")
        else:
            self._log("METRICS", milestone)
    
    def log_error(self, error: Exception) -> None:
        """Log error with traceback.
        
        Args:
            error: Exception to log
        """
        import traceback
        error_msg = f"{type(error).__name__}: {str(error)}"
        self._log("ERROR", error_msg)
        
        # Log traceback on separate lines
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        for line in tb_lines:
            self._log("ERROR", line.rstrip())
    
    def log_info(self, message: str) -> None:
        """Log informational message.
        
        Args:
            message: Info message to log
        """
        self._log("INFO", message)
    
    def close(self) -> None:
        """Close log file handle."""
        try:
            self._log("INFO", "Chat session ended")
            self.file_handle.close()
        except Exception:
            pass  # Fail silently
