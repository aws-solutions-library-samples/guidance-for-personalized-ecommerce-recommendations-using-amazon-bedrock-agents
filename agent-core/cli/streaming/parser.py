"""
SSE (Server-Sent Events) parser for extracting text from streaming responses.

This module provides the SSEParser class which parses AWS Bedrock AgentCore
streaming responses in SSE format and extracts text content from contentBlockDelta events.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SSEParser:
    """
    Parser for Server-Sent Events (SSE) format streaming responses.
    
    Handles parsing of SSE lines in the format:
        data: {"event": {"contentBlockDelta": {"delta": {"text": "..."}}}}
    
    Extracts text content from contentBlockDelta events and handles JSON
    parsing errors gracefully.
    """
    
    def parse_line(self, line: bytes) -> Optional[str]:
        """
        Parse an SSE line and extract text content if present.
        
        Args:
            line: Raw bytes from the streaming response
            
        Returns:
            Extracted text string if found, None otherwise
            
        Examples:
            >>> parser = SSEParser()
            >>> line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}}'
            >>> parser.parse_line(line)
            'Hello'
            
            >>> parser.parse_line(b'data: {"event": {"messageStart": {}}}')
            None
        """
        try:
            # Decode bytes to string
            line_str = line.decode('utf-8').strip()
            
            # Skip empty lines
            if not line_str:
                return None
            
            # Check for SSE data prefix
            if not line_str.startswith('data:'):
                return None
            
            # Extract JSON after "data:" prefix
            json_str = line_str[5:].strip()
            
            # Skip empty data lines
            if not json_str:
                return None
            
            # Parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON: {e}")
                logger.debug(f"Malformed JSON: {json_str[:100]}")
                return None
            
            # Extract text from contentBlockDelta event
            # Expected structure: {"event": {"contentBlockDelta": {"delta": {"text": "..."}}}}
            if not isinstance(data, dict):
                return None
            
            event = data.get('event')
            if not isinstance(event, dict):
                return None
            
            content_block_delta = event.get('contentBlockDelta')
            if not isinstance(content_block_delta, dict):
                return None
            
            delta = content_block_delta.get('delta')
            if not isinstance(delta, dict):
                return None
            
            text = delta.get('text')
            if text is not None and isinstance(text, str):
                return text
            
            return None
            
        except UnicodeDecodeError as e:
            logger.warning(f"Failed to decode line: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing line: {e}")
            return None
