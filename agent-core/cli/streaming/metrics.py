"""Performance metrics tracking for streaming responses.

This module provides timing metrics for API calls and streaming responses,
including connection time, time to first byte (TTFB), and total response time.
"""

import time
from typing import Optional


class PerformanceMetrics:
    """Track performance timing metrics for streaming responses.
    
    Tracks key timing milestones:
    - Connection start: When API call begins
    - Connection established: When API call returns
    - First byte received: When first streaming data arrives
    - Stream complete: When all streaming data processed
    
    Provides derived metrics:
    - Connection time: Time to establish API connection
    - TTFB (Time To First Byte): Time until first data received
    - Total time: Complete response time
    """
    
    def __init__(self):
        """Initialize metrics tracker with no timestamps."""
        self.connection_start: Optional[float] = None
        self.connection_established: Optional[float] = None
        self.first_byte_received: Optional[float] = None
        self.stream_complete: Optional[float] = None
    
    def mark_connection_start(self) -> None:
        """Mark when API connection attempt starts.
        
        Should be called immediately before making the API call.
        """
        self.connection_start = time.perf_counter()
    
    def mark_connection_established(self) -> None:
        """Mark when API connection is established.
        
        Should be called immediately after the API call returns
        (before processing streaming response).
        """
        self.connection_established = time.perf_counter()
    
    def mark_first_byte(self) -> None:
        """Mark when first streaming byte is received.
        
        Should be called when the first chunk of streaming data arrives.
        """
        if self.first_byte_received is None:  # Only mark once
            self.first_byte_received = time.perf_counter()
    
    def mark_stream_complete(self) -> None:
        """Mark when streaming is complete.
        
        Should be called after all streaming data has been processed.
        """
        self.stream_complete = time.perf_counter()
    
    def get_connection_time(self) -> Optional[float]:
        """Get connection establishment time in seconds.
        
        Returns:
            Time in seconds from connection start to established,
            or None if timestamps not available.
        """
        if self.connection_start and self.connection_established:
            return self.connection_established - self.connection_start
        return None
    
    def get_ttfb(self) -> Optional[float]:
        """Get time to first byte (TTFB) in seconds.
        
        Returns:
            Time in seconds from connection start to first byte received,
            or None if timestamps not available.
        """
        if self.connection_start and self.first_byte_received:
            return self.first_byte_received - self.connection_start
        return None
    
    def get_total_time(self) -> Optional[float]:
        """Get total response time in seconds.
        
        Returns:
            Time in seconds from connection start to stream complete,
            or None if timestamps not available.
        """
        if self.connection_start and self.stream_complete:
            return self.stream_complete - self.connection_start
        return None
    
    def format_summary(self) -> str:
        """Format metrics as human-readable string.
        
        Returns:
            Formatted string like "Connection: 32ms, TTFB: 44ms, Total: 1045ms"
            or appropriate message if metrics not available.
        """
        conn_time = self.get_connection_time()
        ttfb = self.get_ttfb()
        total_time = self.get_total_time()
        
        if conn_time is None or ttfb is None or total_time is None:
            return "Performance metrics not available"
        
        # Convert to milliseconds for display
        conn_ms = int(conn_time * 1000)
        ttfb_ms = int(ttfb * 1000)
        total_ms = int(total_time * 1000)
        
        return f"Connection: {conn_ms}ms, TTFB: {ttfb_ms}ms, Total: {total_ms}ms"
