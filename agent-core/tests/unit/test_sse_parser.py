"""
Unit tests for SSEParser class.

Tests cover:
- Valid SSE format parsing
- Text extraction from contentBlockDelta events
- Malformed JSON handling
- Edge cases (empty lines, missing fields, etc.)
"""

import json
import pytest
from cli.streaming.parser import SSEParser


class TestSSEParser:
    """Test suite for SSEParser class."""
    
    def setup_method(self):
        """Create a fresh parser instance for each test."""
        self.parser = SSEParser()
    
    def test_parse_valid_content_block_delta(self):
        """Test parsing valid contentBlockDelta event with text."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}}'
        result = self.parser.parse_line(line)
        assert result == "Hello"
    
    def test_parse_multi_word_text(self):
        """Test parsing text with multiple words and spaces."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Hello, world!"}}}}'
        result = self.parser.parse_line(line)
        assert result == "Hello, world!"
    
    def test_parse_empty_text(self):
        """Test parsing contentBlockDelta with empty text string."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": ""}}}}'
        result = self.parser.parse_line(line)
        assert result == ""
    
    def test_parse_text_with_special_characters(self):
        """Test parsing text with special characters and unicode."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Hello \\u2764\\ufe0f"}}}}'
        result = self.parser.parse_line(line)
        assert result == "Hello ❤️"
    
    def test_parse_message_start_event(self):
        """Test parsing messageStart event (should return None)."""
        line = b'data: {"event": {"messageStart": {"role": "assistant"}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_message_stop_event(self):
        """Test parsing messageStop event (should return None)."""
        line = b'data: {"event": {"messageStop": {}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_empty_line(self):
        """Test parsing empty line."""
        line = b''
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_whitespace_only_line(self):
        """Test parsing line with only whitespace."""
        line = b'   \n'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_line_without_data_prefix(self):
        """Test parsing line without 'data:' prefix."""
        line = b'{"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_data_prefix_with_no_json(self):
        """Test parsing line with 'data:' but no JSON."""
        line = b'data: '
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_malformed_json(self):
        """Test parsing line with malformed JSON (should not crash)."""
        line = b'data: {"event": {"contentBlockDelta": {'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_invalid_json_syntax(self):
        """Test parsing line with invalid JSON syntax."""
        line = b'data: not valid json'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_json_array_instead_of_object(self):
        """Test parsing JSON array instead of expected object."""
        line = b'data: ["array", "not", "object"]'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_missing_event_field(self):
        """Test parsing JSON without 'event' field."""
        line = b'data: {"other": "field"}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_event_not_dict(self):
        """Test parsing when 'event' field is not a dictionary."""
        line = b'data: {"event": "string"}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_missing_content_block_delta(self):
        """Test parsing event without contentBlockDelta field."""
        line = b'data: {"event": {"other": "field"}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_content_block_delta_not_dict(self):
        """Test parsing when contentBlockDelta is not a dictionary."""
        line = b'data: {"event": {"contentBlockDelta": "string"}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_missing_delta_field(self):
        """Test parsing contentBlockDelta without delta field."""
        line = b'data: {"event": {"contentBlockDelta": {"other": "field"}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_delta_not_dict(self):
        """Test parsing when delta is not a dictionary."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": "string"}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_missing_text_field(self):
        """Test parsing delta without text field."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"other": "field"}}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_text_field_not_string(self):
        """Test parsing when text field is not a string."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": 123}}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_text_field_null(self):
        """Test parsing when text field is null."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": null}}}}'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_unicode_decode_error(self):
        """Test handling of invalid UTF-8 bytes."""
        line = b'data: \xff\xfe invalid utf-8'
        result = self.parser.parse_line(line)
        assert result is None
    
    def test_parse_extra_whitespace_around_data_prefix(self):
        """Test parsing with extra whitespace around data prefix."""
        line = b'  data:   {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}}  '
        result = self.parser.parse_line(line)
        assert result == "Hello"
    
    def test_parse_newline_in_text(self):
        """Test parsing text containing newline characters."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Line 1\\nLine 2"}}}}'
        result = self.parser.parse_line(line)
        assert result == "Line 1\nLine 2"
    
    def test_parse_tab_in_text(self):
        """Test parsing text containing tab characters."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Col1\\tCol2"}}}}'
        result = self.parser.parse_line(line)
        assert result == "Col1\tCol2"
    
    def test_parse_escaped_quotes_in_text(self):
        """Test parsing text containing escaped quotes."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "He said \\"Hello\\""}}}}'
        result = self.parser.parse_line(line)
        assert result == 'He said "Hello"'
    
    def test_parse_thinking_tags_in_text(self):
        """Test parsing text containing thinking tags (parser should pass through)."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "<thinking>"}}}}'
        result = self.parser.parse_line(line)
        assert result == "<thinking>"
    
    def test_parse_multiple_calls_independent(self):
        """Test that multiple parse_line calls are independent (no state)."""
        line1 = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "First"}}}}'
        line2 = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Second"}}}}'
        
        result1 = self.parser.parse_line(line1)
        result2 = self.parser.parse_line(line2)
        
        assert result1 == "First"
        assert result2 == "Second"
    
    def test_parse_very_long_text(self):
        """Test parsing very long text content."""
        long_text = "A" * 10000
        event_data = {"event": {"contentBlockDelta": {"delta": {"text": long_text}}}}
        line = f'data: {json.dumps(event_data)}'.encode('utf-8')
        
        result = self.parser.parse_line(line)
        assert result == long_text
    
    def test_parse_nested_json_in_text(self):
        """Test parsing text that contains JSON-like content."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "{\\"key\\": \\"value\\"}"}}}}'
        result = self.parser.parse_line(line)
        assert result == '{"key": "value"}'
    
    def test_parse_extra_fields_in_event(self):
        """Test parsing event with extra fields (should still extract text)."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}, "extra": "field"}, "other": "data"}}'
        result = self.parser.parse_line(line)
        assert result == "Hello"
    
    def test_parse_colon_in_json_value(self):
        """Test parsing when JSON values contain colons."""
        line = b'data: {"event": {"contentBlockDelta": {"delta": {"text": "Time: 10:30"}}}}'
        result = self.parser.parse_line(line)
        assert result == "Time: 10:30"
