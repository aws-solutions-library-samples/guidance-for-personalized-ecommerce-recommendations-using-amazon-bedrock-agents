"""
Unit tests for ThinkingTagFilter class.

Tests cover:
- State machine transitions (NORMAL <-> THINKING)
- Complete thinking tags in single chunk
- Thinking tags split across multiple chunks
- Multiple thinking blocks
- Edge cases (partial tags, nested content, etc.)
"""

import pytest
from cli.streaming.filter import ThinkingTagFilter, FilterState


class TestThinkingTagFilter:
    """Test suite for ThinkingTagFilter class."""
    
    def setup_method(self):
        """Create a fresh filter instance for each test."""
        self.filter = ThinkingTagFilter()
    
    # Basic functionality tests
    
    def test_initial_state(self):
        """Test filter starts in NORMAL state."""
        assert self.filter.state == FilterState.NORMAL
        assert self.filter.buffer == ""
        assert self.filter.thinking_content == []
    
    def test_process_text_without_tags(self):
        """Test processing text without any thinking tags."""
        text, thinking = self.filter.process_text("Hello world")
        assert text == "Hello world"
        assert thinking is None
        assert self.filter.state == FilterState.NORMAL
    
    def test_process_empty_text(self):
        """Test processing empty text."""
        text, thinking = self.filter.process_text("")
        assert text == ""
        assert thinking is None
    
    # Complete tags in single chunk
    
    def test_complete_thinking_tags_single_chunk(self):
        """Test filtering complete thinking tags in one chunk."""
        text, thinking = self.filter.process_text(
            "Hello <thinking>internal thoughts</thinking> world"
        )
        assert text == "Hello  world"
        assert thinking == "internal thoughts"
        assert self.filter.state == FilterState.NORMAL
    
    def test_thinking_at_start(self):
        """Test thinking tags at the start of text."""
        text, thinking = self.filter.process_text(
            "<thinking>thoughts</thinking> Hello"
        )
        assert text == " Hello"
        assert thinking == "thoughts"
    
    def test_thinking_at_end(self):
        """Test thinking tags at the end of text."""
        text, thinking = self.filter.process_text(
            "Hello <thinking>thoughts</thinking>"
        )
        assert text == "Hello "
        assert thinking == "thoughts"
    
    def test_only_thinking_tags(self):
        """Test text containing only thinking tags."""
        text, thinking = self.filter.process_text(
            "<thinking>only thoughts</thinking>"
        )
        assert text == ""
        assert thinking == "only thoughts"
    
    def test_empty_thinking_tags(self):
        """Test empty thinking tags."""
        text, thinking = self.filter.process_text(
            "Hello <thinking></thinking> world"
        )
        assert text == "Hello  world"
        assert thinking == ""
    
    # Multiple thinking blocks
    
    def test_multiple_thinking_blocks_single_chunk(self):
        """Test multiple thinking blocks in one chunk."""
        text, thinking = self.filter.process_text(
            "<thinking>first</thinking> text <thinking>second</thinking>"
        )
        # Only the last thinking content is returned
        assert text == " text "
        assert thinking == "second"
        # But all thinking content is accumulated
        assert len(self.filter.thinking_content) == 2
        assert self.filter.thinking_content[0] == "first"
        assert self.filter.thinking_content[1] == "second"
    
    def test_consecutive_thinking_blocks(self):
        """Test consecutive thinking blocks with no text between."""
        text, thinking = self.filter.process_text(
            "<thinking>first</thinking><thinking>second</thinking>"
        )
        assert text == ""
        assert thinking == "second"
        assert len(self.filter.thinking_content) == 2
    
    # Tags split across chunks
    
    def test_opening_tag_split_across_chunks(self):
        """Test opening tag split across multiple chunks."""
        # First chunk: partial opening tag
        text1, thinking1 = self.filter.process_text("Hello <think")
        assert text1 == "Hello "
        assert thinking1 is None
        assert self.filter.state == FilterState.NORMAL
        
        # Second chunk: complete the tag
        text2, thinking2 = self.filter.process_text("ing>thoughts</thinking>")
        assert text2 == ""
        assert thinking2 == "thoughts"
        assert self.filter.state == FilterState.NORMAL
    
    def test_closing_tag_split_across_chunks(self):
        """Test closing tag split across multiple chunks."""
        # First chunk: opening tag and partial content
        text1, thinking1 = self.filter.process_text("Hello <thinking>thoughts</think")
        assert text1 == "Hello "
        assert thinking1 is None
        assert self.filter.state == FilterState.THINKING
        
        # Second chunk: complete closing tag
        text2, thinking2 = self.filter.process_text("ing> world")
        assert text2 == " world"
        assert thinking2 == "thoughts"
        assert self.filter.state == FilterState.NORMAL
    
    def test_thinking_content_split_across_chunks(self):
        """Test thinking content split across multiple chunks."""
        # First chunk: opening tag and partial content
        text1, thinking1 = self.filter.process_text("Hello <thinking>internal")
        assert text1 == "Hello "
        assert thinking1 is None
        assert self.filter.state == FilterState.THINKING
        
        # Second chunk: more content
        text2, thinking2 = self.filter.process_text(" thoughts")
        assert text2 == ""
        assert thinking2 is None
        assert self.filter.state == FilterState.THINKING
        
        # Third chunk: closing tag
        text3, thinking3 = self.filter.process_text("</thinking> world")
        assert text3 == " world"
        assert thinking3 == "internal thoughts"
        assert self.filter.state == FilterState.NORMAL
    
    def test_complete_flow_across_chunks(self):
        """Test complete flow with tags split across many chunks."""
        chunks = [
            ("Hello ", "Hello ", None, FilterState.NORMAL),
            ("<", "", None, FilterState.NORMAL),
            ("think", "", None, FilterState.NORMAL),
            ("ing>", "", None, FilterState.THINKING),
            ("internal ", "", None, FilterState.THINKING),
            ("thoughts", "", None, FilterState.THINKING),
            ("</think", "", None, FilterState.THINKING),
            ("ing>", "", "internal thoughts", FilterState.NORMAL),
            (" world", " world", None, FilterState.NORMAL),
        ]
        
        for chunk_text, expected_display, expected_thinking, expected_state in chunks:
            text, thinking = self.filter.process_text(chunk_text)
            assert text == expected_display, f"Failed on chunk: {chunk_text}"
            assert thinking == expected_thinking, f"Failed on chunk: {chunk_text}"
            assert self.filter.state == expected_state, f"Failed on chunk: {chunk_text}"
    
    # Partial tag detection
    
    def test_partial_opening_tag_detection(self):
        """Test detection of partial opening tags."""
        assert self.filter._has_partial_opening_tag("text <")
        assert self.filter._has_partial_opening_tag("text <t")
        assert self.filter._has_partial_opening_tag("text <th")
        assert self.filter._has_partial_opening_tag("text <thi")
        assert self.filter._has_partial_opening_tag("text <thin")
        assert self.filter._has_partial_opening_tag("text <think")
        assert self.filter._has_partial_opening_tag("text <thinki")
        assert self.filter._has_partial_opening_tag("text <thinkin")
        assert not self.filter._has_partial_opening_tag("text <thinking>")
        assert not self.filter._has_partial_opening_tag("text")
    
    def test_partial_closing_tag_detection(self):
        """Test detection of partial closing tags."""
        assert self.filter._has_partial_closing_tag("text <")
        assert self.filter._has_partial_closing_tag("text </")
        assert self.filter._has_partial_closing_tag("text </t")
        assert self.filter._has_partial_closing_tag("text </th")
        assert self.filter._has_partial_closing_tag("text </thi")
        assert self.filter._has_partial_closing_tag("text </thin")
        assert self.filter._has_partial_closing_tag("text </think")
        assert self.filter._has_partial_closing_tag("text </thinki")
        assert self.filter._has_partial_closing_tag("text </thinkin")
        assert self.filter._has_partial_closing_tag("text </thinking")
        assert not self.filter._has_partial_closing_tag("text </thinking>")
        assert not self.filter._has_partial_closing_tag("text")
    
    def test_safe_display_length(self):
        """Test calculation of safe display length."""
        assert self.filter._get_safe_display_length("Hello world") == 11
        assert self.filter._get_safe_display_length("Hello <") == 6
        assert self.filter._get_safe_display_length("Hello <t") == 6
        assert self.filter._get_safe_display_length("Hello <think") == 6
        assert self.filter._get_safe_display_length("Hello <thinking>") == 16
    
    # Edge cases
    
    def test_text_with_angle_brackets(self):
        """Test text containing angle brackets that aren't tags."""
        text, thinking = self.filter.process_text("x < y and y > z")
        assert text == "x < y and y > z"
        assert thinking is None
    
    def test_incomplete_opening_tag(self):
        """Test text ending with incomplete opening tag."""
        text, thinking = self.filter.process_text("Hello <thin")
        assert text == "Hello "
        assert thinking is None
        assert self.filter.buffer == "<thin"
    
    def test_incomplete_closing_tag_in_thinking(self):
        """Test thinking content ending with incomplete closing tag."""
        text1, thinking1 = self.filter.process_text("<thinking>thoughts</thin")
        assert text1 == ""
        assert thinking1 is None
        assert self.filter.state == FilterState.THINKING
        
        text2, thinking2 = self.filter.process_text("king>")
        assert text2 == ""
        assert thinking2 == "thoughts"
    
    def test_similar_but_not_thinking_tag(self):
        """Test text with similar but different tags."""
        text, thinking = self.filter.process_text("<thought>not a thinking tag</thought>")
        assert text == "<thought>not a thinking tag</thought>"
        assert thinking is None
    
    def test_nested_angle_brackets_in_thinking(self):
        """Test thinking content with nested angle brackets."""
        text, thinking = self.filter.process_text(
            "<thinking>x < y and y > z</thinking>"
        )
        assert text == ""
        assert thinking == "x < y and y > z"
    
    def test_thinking_tag_in_thinking_content(self):
        """Test thinking content containing the word 'thinking'."""
        text, thinking = self.filter.process_text(
            "<thinking>I am thinking about this</thinking>"
        )
        assert text == ""
        assert thinking == "I am thinking about this"
    
    def test_newlines_in_thinking(self):
        """Test thinking content with newlines."""
        text, thinking = self.filter.process_text(
            "<thinking>line 1\nline 2\nline 3</thinking>"
        )
        assert text == ""
        assert thinking == "line 1\nline 2\nline 3"
    
    def test_special_characters_in_thinking(self):
        """Test thinking content with special characters."""
        text, thinking = self.filter.process_text(
            "<thinking>Special: !@#$%^&*()</thinking>"
        )
        assert text == ""
        assert thinking == "Special: !@#$%^&*()"
    
    def test_unicode_in_thinking(self):
        """Test thinking content with unicode characters."""
        text, thinking = self.filter.process_text(
            "<thinking>Unicode: 你好 🌍 ❤️</thinking>"
        )
        assert text == ""
        assert thinking == "Unicode: 你好 🌍 ❤️"
    
    def test_very_long_thinking_content(self):
        """Test very long thinking content."""
        long_content = "A" * 10000
        text, thinking = self.filter.process_text(
            f"<thinking>{long_content}</thinking>"
        )
        assert text == ""
        assert thinking == long_content
    
    # State management tests
    
    def test_get_all_thinking_content(self):
        """Test retrieving all accumulated thinking content."""
        self.filter.process_text("<thinking>first</thinking>")
        self.filter.process_text(" text ")
        self.filter.process_text("<thinking>second</thinking>")
        
        all_thinking = self.filter.get_all_thinking_content()
        assert all_thinking == "firstsecond"
    
    def test_reset(self):
        """Test resetting the filter state."""
        self.filter.process_text("<thinking>thoughts")
        assert self.filter.state == FilterState.THINKING
        assert self.filter.buffer != ""
        
        self.filter.reset()
        assert self.filter.state == FilterState.NORMAL
        assert self.filter.buffer == ""
        assert self.filter.thinking_content == []
    
    def test_multiple_calls_maintain_state(self):
        """Test that state is maintained across multiple calls."""
        # Start thinking block
        text1, thinking1 = self.filter.process_text("Hello <thinking>")
        assert self.filter.state == FilterState.THINKING
        
        # Continue in thinking state
        text2, thinking2 = self.filter.process_text("thoughts")
        assert self.filter.state == FilterState.THINKING
        
        # Close thinking block
        text3, thinking3 = self.filter.process_text("</thinking> world")
        assert self.filter.state == FilterState.NORMAL
        assert thinking3 == "thoughts"
    
    # Real-world scenarios
    
    def test_realistic_agent_response(self):
        """Test realistic agent response with thinking."""
        chunks = [
            "<thinking>The user is asking about",
            " the weather. I should provide",
            " a helpful response.</thinking>",
            "I'd be happy to help you",
            " with weather information!"
        ]
        
        all_display = ""
        final_thinking = None
        
        for chunk in chunks:
            text, thinking = self.filter.process_text(chunk)
            all_display += text
            if thinking:
                final_thinking = thinking
        
        assert all_display == "I'd be happy to help you with weather information!"
        assert final_thinking == "The user is asking about the weather. I should provide a helpful response."
    
    def test_multiple_thinking_blocks_realistic(self):
        """Test multiple thinking blocks in realistic scenario."""
        response = (
            "<thinking>First, I'll analyze the question</thinking>"
            "Let me help you with that. "
            "<thinking>Now I'll formulate the answer</thinking>"
            "Here's what you need to know."
        )
        
        text, thinking = self.filter.process_text(response)
        assert text == "Let me help you with that. Here's what you need to know."
        assert thinking == "Now I'll formulate the answer"
        assert len(self.filter.thinking_content) == 2
    
    def test_no_closing_tag_buffers_content(self):
        """Test that content without closing tag stays buffered."""
        text, thinking = self.filter.process_text("Hello <thinking>thoughts without closing")
        assert text == "Hello "
        assert thinking is None
        assert self.filter.state == FilterState.THINKING
        assert "thoughts without closing" in self.filter.buffer
    
    def test_partial_tag_at_chunk_boundary(self):
        """Test handling of partial tag exactly at chunk boundary."""
        # Chunk ends with start of opening tag
        text1, thinking1 = self.filter.process_text("Hello <")
        assert text1 == "Hello "
        assert self.filter.buffer == "<"
        
        # Next chunk completes tag
        text2, thinking2 = self.filter.process_text("thinking>content</thinking>")
        assert text2 == ""
        assert thinking2 == "content"
