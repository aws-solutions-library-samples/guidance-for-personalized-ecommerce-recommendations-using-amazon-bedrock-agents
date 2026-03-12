"""
Thinking tag filter for removing <thinking> tags from streaming response text.

This module provides the ThinkingTagFilter class which implements a state machine
to filter out <thinking>...</thinking> tags from response text while preserving
the thinking content for logging purposes.
"""

import logging
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FilterState(Enum):
    """
    State machine states for thinking tag filtering.
    
    NORMAL: Processing normal response text (display mode)
    THINKING: Inside thinking tags (buffer mode, don't display)
    """
    NORMAL = "normal"
    THINKING = "thinking"


class ThinkingTagFilter:
    """
    State machine filter for removing thinking tags from streaming text.
    
    Filters <thinking>...</thinking> tags from response text while extracting
    the thinking content for logging. Handles tags that are split across
    multiple chunks by maintaining state and a buffer.
    
    The filter operates as a state machine with two states:
    - NORMAL: Display text as it arrives
    - THINKING: Buffer text (don't display) until closing tag
    
    Example:
        >>> filter = ThinkingTagFilter()
        >>> text, thinking = filter.process_text("Hello <thinking>internal")
        >>> print(text)  # "Hello "
        >>> text, thinking = filter.process_text(" thoughts</thinking> world")
        >>> print(text)  # " world"
        >>> print(thinking)  # "internal thoughts"
    """
    
    def __init__(self):
        """Initialize the filter in NORMAL state with empty buffers."""
        self.state = FilterState.NORMAL
        self.buffer = ""
        self.thinking_content = []
    
    def process_text(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Process a text chunk and filter thinking tags.
        
        This method implements a state machine that:
        1. In NORMAL state: displays text until <thinking> tag found
        2. In THINKING state: buffers text until </thinking> tag found
        3. Handles tags split across multiple chunks
        
        Args:
            text: Text chunk from streaming response
            
        Returns:
            Tuple of (displayable_text, thinking_content):
            - displayable_text: Text to show to user (thinking tags removed)
            - thinking_content: Extracted thinking content if closing tag found, None otherwise
            
        Examples:
            >>> filter = ThinkingTagFilter()
            
            # Simple case: complete tags in one chunk
            >>> filter.process_text("Hello <thinking>thoughts</thinking> world")
            ("Hello  world", "thoughts")
            
            # Split case: tag split across chunks
            >>> filter.process_text("Hello <think")
            ("Hello ", None)
            >>> filter.process_text("ing>thoughts</think")
            ("", None)
            >>> filter.process_text("ing> world")
            (" world", "thoughts")
            
            # Multiple thinking blocks
            >>> filter.process_text("<thinking>first</thinking> text <thinking>second</thinking>")
            (" text ", "second")
        """
        self.buffer += text
        displayable = ""
        thinking = None
        
        while True:
            if self.state == FilterState.NORMAL:
                # Look for opening thinking tag
                if '<thinking>' in self.buffer:
                    # Display text before tag
                    before, after = self.buffer.split('<thinking>', 1)
                    displayable += before
                    self.buffer = after
                    self.state = FilterState.THINKING
                    logger.debug("Entered THINKING state")
                else:
                    # No opening tag found, check if we might have a partial tag
                    # Keep potential partial tag in buffer
                    if self._has_partial_opening_tag(self.buffer):
                        # Keep the partial tag in buffer for next chunk
                        safe_length = self._get_safe_display_length(self.buffer)
                        displayable += self.buffer[:safe_length]
                        self.buffer = self.buffer[safe_length:]
                    else:
                        # Display all accumulated text
                        displayable += self.buffer
                        self.buffer = ""
                    break
                    
            elif self.state == FilterState.THINKING:
                # Look for closing thinking tag
                if '</thinking>' in self.buffer:
                    # Extract thinking content
                    content, after = self.buffer.split('</thinking>', 1)
                    thinking = content
                    self.thinking_content.append(content)
                    self.buffer = after
                    self.state = FilterState.NORMAL
                    logger.debug(f"Exited THINKING state, extracted {len(content)} chars")
                else:
                    # Still in thinking, check if we might have a partial closing tag
                    if self._has_partial_closing_tag(self.buffer):
                        # Keep potential partial tag in buffer for next chunk
                        # Don't extract thinking content yet
                        pass
                    # Wait for more chunks
                    break
        
        return displayable, thinking
    
    def _has_partial_opening_tag(self, text: str) -> bool:
        """
        Check if text ends with a partial <thinking> tag.
        
        Args:
            text: Text to check
            
        Returns:
            True if text might end with partial opening tag
            
        Examples:
            >>> filter._has_partial_opening_tag("Hello <")
            True
            >>> filter._has_partial_opening_tag("Hello <t")
            True
            >>> filter._has_partial_opening_tag("Hello <thinking")
            True
            >>> filter._has_partial_opening_tag("Hello world")
            False
        """
        tag = '<thinking>'
        for i in range(1, len(tag)):
            if text.endswith(tag[:i]):
                return True
        return False
    
    def _has_partial_closing_tag(self, text: str) -> bool:
        """
        Check if text ends with a partial </thinking> tag.
        
        Args:
            text: Text to check
            
        Returns:
            True if text might end with partial closing tag
        """
        tag = '</thinking>'
        for i in range(1, len(tag)):
            if text.endswith(tag[:i]):
                return True
        return False
    
    def _get_safe_display_length(self, text: str) -> int:
        """
        Get the length of text that's safe to display (excluding partial tag).
        
        Args:
            text: Text to analyze
            
        Returns:
            Number of characters safe to display
        """
        tag = '<thinking>'
        for i in range(len(tag) - 1, 0, -1):
            if text.endswith(tag[:i]):
                return len(text) - i
        return len(text)
    
    def get_all_thinking_content(self) -> str:
        """
        Get all accumulated thinking content.
        
        Returns:
            All thinking content joined together
        """
        return ''.join(self.thinking_content)
    
    def reset(self):
        """Reset the filter to initial state."""
        self.state = FilterState.NORMAL
        self.buffer = ""
        self.thinking_content = []
