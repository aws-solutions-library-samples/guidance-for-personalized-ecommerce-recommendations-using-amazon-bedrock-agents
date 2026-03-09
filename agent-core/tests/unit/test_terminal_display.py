"""
Unit tests for TerminalDisplay class.

Tests the terminal output manager including thinking indicators,
agent responses, verbosity control, and color formatting.
"""

import time
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock
from cli.streaming.display import TerminalDisplay, SpinnerAnimation


class TestTerminalDisplay:
    """Test suite for TerminalDisplay class."""
    
    def test_initialization(self):
        """Test display initializes with correct default state."""
        display = TerminalDisplay()
        
        assert display.verbosity == 0
        assert display.thinking_shown is False
        assert display.agent_label_shown is False
        assert isinstance(display.spinner, SpinnerAnimation)
        assert display.last_spinner_char is None
    
    def test_initialization_with_verbosity(self):
        """Test display initializes with custom verbosity level."""
        display = TerminalDisplay(verbosity=2)
        
        assert display.verbosity == 2
    
    def test_color_constants(self):
        """Test color constants are defined correctly."""
        assert hasattr(TerminalDisplay, 'COLOR_GRAY')
        assert hasattr(TerminalDisplay, 'COLOR_CYAN')
        assert hasattr(TerminalDisplay, 'COLOR_GREEN')
        assert hasattr(TerminalDisplay, 'COLOR_YELLOW')
        assert hasattr(TerminalDisplay, 'COLOR_RESET')
        
        # Verify they are ANSI escape codes
        assert TerminalDisplay.COLOR_GRAY.startswith('\033[')
        assert TerminalDisplay.COLOR_RESET == '\033[0m'
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_thinking_first_call(self, mock_stdout):
        """Test show_thinking displays initial message on first call."""
        display = TerminalDisplay()
        
        display.show_thinking()
        
        output = mock_stdout.getvalue()
        assert 'Thinking:' in output
        assert display.thinking_shown is True
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_thinking_with_spinner(self, mock_stdout):
        """Test show_thinking displays spinner character."""
        display = TerminalDisplay()
        
        # First call shows message and spinner
        display.show_thinking()
        
        output = mock_stdout.getvalue()
        assert 'Thinking:' in output
        # Should contain first spinner character
        assert '⠋' in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_thinking_updates_spinner(self, mock_stdout):
        """Test show_thinking updates spinner on subsequent calls."""
        display = TerminalDisplay()
        
        # First call
        display.show_thinking()
        first_output = mock_stdout.getvalue()
        
        # Wait for spinner interval
        time.sleep(0.11)
        
        # Second call should update spinner
        display.show_thinking()
        second_output = mock_stdout.getvalue()
        
        # Output should have changed (new spinner character)
        assert len(second_output) > len(first_output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_thinking_content_verbosity_0(self, mock_stdout):
        """Test show_thinking_content does not display at verbosity 0."""
        display = TerminalDisplay(verbosity=0)
        
        display.show_thinking_content("Test thinking content")
        
        output = mock_stdout.getvalue()
        assert output == ""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_thinking_content_verbosity_1(self, mock_stdout):
        """Test show_thinking_content displays at verbosity 1."""
        display = TerminalDisplay(verbosity=1)
        
        display.show_thinking_content("Test thinking content")
        
        output = mock_stdout.getvalue()
        assert "[Thinking]" in output
        assert "Test thinking content" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_thinking_content_verbosity_2(self, mock_stdout):
        """Test show_thinking_content displays at verbosity 2."""
        display = TerminalDisplay(verbosity=2)
        
        display.show_thinking_content("Test thinking content")
        
        output = mock_stdout.getvalue()
        assert "[Thinking]" in output
        assert "Test thinking content" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_agent_response_first_call(self, mock_stdout):
        """Test show_agent_response displays label on first call."""
        display = TerminalDisplay()
        
        display.show_agent_response("Hello", elapsed_time=7.5)
        
        output = mock_stdout.getvalue()
        assert "Agent[7.5s]:" in output
        assert "Hello" in output
        assert display.agent_label_shown is True
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_agent_response_without_timing(self, mock_stdout):
        """Test show_agent_response works without elapsed time."""
        display = TerminalDisplay()
        
        display.show_agent_response("Hello")
        
        output = mock_stdout.getvalue()
        assert "Agent:" in output
        assert "Hello" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_agent_response_subsequent_calls(self, mock_stdout):
        """Test show_agent_response only shows label once."""
        display = TerminalDisplay()
        
        display.show_agent_response("Hello", elapsed_time=7.5)
        first_output = mock_stdout.getvalue()
        
        display.show_agent_response(" World")
        second_output = mock_stdout.getvalue()
        
        # Label should only appear once
        assert first_output.count("Agent[7.5s]:") == 1
        assert second_output.count("Agent[7.5s]:") == 1
        assert "Hello World" in second_output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_agent_response_clears_thinking(self, mock_stdout):
        """Test show_agent_response clears thinking line."""
        display = TerminalDisplay()
        
        # Show thinking first
        display.show_thinking()
        assert display.thinking_shown is True
        
        # Show agent response should clear thinking line
        display.show_agent_response("Hello", elapsed_time=5.0)
        
        output = mock_stdout.getvalue()
        assert "Agent[5.0s]:" in output
        assert "Hello" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_raw_event_verbosity_0(self, mock_stdout):
        """Test show_raw_event does not display at verbosity 0."""
        display = TerminalDisplay(verbosity=0)
        
        event = {"event": {"messageStart": {"role": "assistant"}}}
        display.show_raw_event(event)
        
        output = mock_stdout.getvalue()
        assert output == ""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_raw_event_verbosity_1(self, mock_stdout):
        """Test show_raw_event does not display at verbosity 1."""
        display = TerminalDisplay(verbosity=1)
        
        event = {"event": {"messageStart": {"role": "assistant"}}}
        display.show_raw_event(event)
        
        output = mock_stdout.getvalue()
        assert output == ""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_raw_event_verbosity_2(self, mock_stdout):
        """Test show_raw_event displays at verbosity 2."""
        display = TerminalDisplay(verbosity=2)
        
        event = {"event": {"messageStart": {"role": "assistant"}}}
        display.show_raw_event(event)
        
        output = mock_stdout.getvalue()
        assert "[RAW EVENT]" in output
        assert "messageStart" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_metrics_verbosity_0(self, mock_stdout):
        """Test show_metrics does not display at verbosity 0."""
        display = TerminalDisplay(verbosity=0)
        
        display.show_metrics("Connection: 32ms, TTFB: 44ms, Total: 1045ms")
        
        output = mock_stdout.getvalue()
        assert output == ""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_metrics_verbosity_1(self, mock_stdout):
        """Test show_metrics displays at verbosity 1."""
        display = TerminalDisplay(verbosity=1)
        
        display.show_metrics("Connection: 32ms, TTFB: 44ms, Total: 1045ms")
        
        output = mock_stdout.getvalue()
        assert "[Metrics]" in output
        assert "Connection: 32ms" in output
        assert "TTFB: 44ms" in output
        assert "Total: 1045ms" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_metrics_verbosity_2(self, mock_stdout):
        """Test show_metrics displays at verbosity 2."""
        display = TerminalDisplay(verbosity=2)
        
        display.show_metrics("Connection: 32ms, TTFB: 44ms, Total: 1045ms")
        
        output = mock_stdout.getvalue()
        assert "[Metrics]" in output
        assert "Connection: 32ms" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_finish_response(self, mock_stdout):
        """Test finish_response adds newline after response."""
        display = TerminalDisplay()
        
        # Show agent response first
        display.show_agent_response("Hello")
        
        # Finish response
        display.finish_response()
        
        output = mock_stdout.getvalue()
        assert output.endswith('\n')
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_finish_response_without_agent_label(self, mock_stdout):
        """Test finish_response does nothing if no agent label shown."""
        display = TerminalDisplay()
        
        # Finish without showing agent response
        display.finish_response()
        
        output = mock_stdout.getvalue()
        # Should not add newline if no agent label shown
        assert output == ""
    
    def test_reset(self):
        """Test reset clears all state flags."""
        display = TerminalDisplay()
        
        # Set some state
        display.thinking_shown = True
        display.agent_label_shown = True
        display.last_spinner_char = '⠋'
        
        # Reset
        display.reset()
        
        # Verify state cleared
        assert display.thinking_shown is False
        assert display.agent_label_shown is False
        assert display.last_spinner_char is None
        assert isinstance(display.spinner, SpinnerAnimation)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_color_formatting_in_thinking(self, mock_stdout):
        """Test thinking output uses gray color."""
        display = TerminalDisplay()
        
        display.show_thinking()
        
        output = mock_stdout.getvalue()
        assert TerminalDisplay.COLOR_GRAY in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_color_formatting_in_agent_response(self, mock_stdout):
        """Test agent response uses green color for label."""
        display = TerminalDisplay()
        
        display.show_agent_response("Hello", elapsed_time=5.0)
        
        output = mock_stdout.getvalue()
        assert TerminalDisplay.COLOR_GREEN in output
        assert TerminalDisplay.COLOR_RESET in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_color_formatting_in_metrics(self, mock_stdout):
        """Test metrics output uses cyan color."""
        display = TerminalDisplay(verbosity=1)
        
        display.show_metrics("Connection: 32ms")
        
        output = mock_stdout.getvalue()
        assert TerminalDisplay.COLOR_CYAN in output
        assert TerminalDisplay.COLOR_RESET in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_color_formatting_in_raw_event(self, mock_stdout):
        """Test raw event output uses yellow color."""
        display = TerminalDisplay(verbosity=2)
        
        display.show_raw_event({"test": "event"})
        
        output = mock_stdout.getvalue()
        assert TerminalDisplay.COLOR_YELLOW in output
        assert TerminalDisplay.COLOR_RESET in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_complete_flow_verbosity_0(self, mock_stdout):
        """Test complete output flow at verbosity 0."""
        display = TerminalDisplay(verbosity=0)
        
        # Show thinking
        display.show_thinking()
        
        # Show thinking content (should not display)
        display.show_thinking_content("Internal reasoning")
        
        # Show agent response
        display.show_agent_response("Hello", elapsed_time=7.5)
        display.show_agent_response(" World")
        
        # Show metrics (should not display)
        display.show_metrics("Connection: 32ms")
        
        # Finish
        display.finish_response()
        
        output = mock_stdout.getvalue()
        
        # Should contain thinking and response
        assert "Thinking:" in output
        assert "Agent[7.5s]:" in output
        assert "Hello World" in output
        
        # Should NOT contain thinking content or metrics
        assert "[Thinking]" not in output
        assert "[Metrics]" not in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_complete_flow_verbosity_1(self, mock_stdout):
        """Test complete output flow at verbosity 1."""
        display = TerminalDisplay(verbosity=1)
        
        # Show thinking
        display.show_thinking()
        
        # Show thinking content (should display)
        display.show_thinking_content("Internal reasoning")
        
        # Show agent response
        display.show_agent_response("Hello", elapsed_time=7.5)
        
        # Show metrics (should display)
        display.show_metrics("Connection: 32ms")
        
        # Finish
        display.finish_response()
        
        output = mock_stdout.getvalue()
        
        # Should contain everything except raw events
        assert "Thinking:" in output
        assert "[Thinking]" in output
        assert "Internal reasoning" in output
        assert "Agent[7.5s]:" in output
        assert "Hello" in output
        assert "[Metrics]" in output
        assert "Connection: 32ms" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_complete_flow_verbosity_2(self, mock_stdout):
        """Test complete output flow at verbosity 2."""
        display = TerminalDisplay(verbosity=2)
        
        # Show raw event
        display.show_raw_event({"event": "test"})
        
        # Show thinking
        display.show_thinking()
        
        # Show thinking content
        display.show_thinking_content("Internal reasoning")
        
        # Show agent response
        display.show_agent_response("Hello", elapsed_time=7.5)
        
        # Show metrics
        display.show_metrics("Connection: 32ms")
        
        # Finish
        display.finish_response()
        
        output = mock_stdout.getvalue()
        
        # Should contain everything
        assert "[RAW EVENT]" in output
        assert "Thinking:" in output
        assert "[Thinking]" in output
        assert "Agent[7.5s]:" in output
        assert "[Metrics]" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_multiple_responses_with_reset(self, mock_stdout):
        """Test multiple responses using reset between them."""
        display = TerminalDisplay()
        
        # First response
        display.show_thinking()
        display.show_agent_response("First", elapsed_time=5.0)
        display.finish_response()
        
        # Reset for next response
        display.reset()
        
        # Second response
        display.show_thinking()
        display.show_agent_response("Second", elapsed_time=3.0)
        display.finish_response()
        
        output = mock_stdout.getvalue()
        
        # Should contain both responses
        assert "Agent[5.0s]:" in output
        assert "First" in output
        assert "Agent[3.0s]:" in output
        assert "Second" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_timing_format_precision(self, mock_stdout):
        """Test timing is formatted with one decimal place."""
        display = TerminalDisplay()
        
        # Test various timing values
        display.show_agent_response("Test", elapsed_time=7.123456)
        
        output = mock_stdout.getvalue()
        
        # Should be rounded to 1 decimal place
        assert "Agent[7.1s]:" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_empty_response_text(self, mock_stdout):
        """Test handling of empty response text."""
        display = TerminalDisplay()
        
        display.show_agent_response("", elapsed_time=5.0)
        
        output = mock_stdout.getvalue()
        
        # Should still show label
        assert "Agent[5.0s]:" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_long_response_text(self, mock_stdout):
        """Test handling of long response text."""
        display = TerminalDisplay()
        
        long_text = "A" * 1000
        display.show_agent_response(long_text, elapsed_time=5.0)
        
        output = mock_stdout.getvalue()
        
        # Should contain label and full text
        assert "Agent[5.0s]:" in output
        assert long_text in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_special_characters_in_response(self, mock_stdout):
        """Test handling of special characters in response."""
        display = TerminalDisplay()
        
        special_text = "Hello 🌍! Test\nNewline\tTab"
        display.show_agent_response(special_text, elapsed_time=5.0)
        
        output = mock_stdout.getvalue()
        
        # Should contain special characters
        assert "🌍" in output
        assert "\n" in output
        assert "\t" in output
