"""
Unit tests for SpinnerAnimation class.

Tests the animated spinner functionality including character cycling,
timing behavior, and update intervals.
"""

import time
import pytest
from cli.streaming.display import SpinnerAnimation


class TestSpinnerAnimation:
    """Test suite for SpinnerAnimation class."""
    
    def test_initialization(self):
        """Test spinner initializes with correct starting state."""
        spinner = SpinnerAnimation()
        
        assert spinner.index == 0
        assert spinner.last_update == 0
        assert len(spinner.CHARS) == 10
        assert spinner.UPDATE_INTERVAL == 0.1
    
    def test_spinner_characters(self):
        """Test spinner has correct Braille pattern characters."""
        expected_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        
        assert SpinnerAnimation.CHARS == expected_chars
    
    def test_first_update_returns_character(self):
        """Test first update returns first character immediately."""
        spinner = SpinnerAnimation()
        
        # First call should return first character
        char = spinner.update()
        
        assert char == '⠋'
        assert spinner.index == 1
    
    def test_update_too_soon_returns_none(self):
        """Test update returns None if called before interval elapses."""
        spinner = SpinnerAnimation()
        
        # First update
        first_char = spinner.update()
        assert first_char is not None
        
        # Immediate second update (before 100ms)
        second_char = spinner.update()
        assert second_char is None
    
    def test_update_after_interval_returns_next_character(self):
        """Test update returns next character after 100ms interval."""
        spinner = SpinnerAnimation()
        
        # First update
        first_char = spinner.update()
        assert first_char == '⠋'
        
        # Wait for interval to elapse
        time.sleep(0.11)  # Slightly more than 100ms
        
        # Second update should return next character
        second_char = spinner.update()
        assert second_char == '⠙'
        assert spinner.index == 2
    
    def test_character_cycling(self):
        """Test spinner cycles through all characters in order."""
        spinner = SpinnerAnimation()
        expected_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        
        collected_chars = []
        
        for i in range(10):
            char = spinner.update()
            if char:
                collected_chars.append(char)
            time.sleep(0.11)  # Wait for interval
        
        assert collected_chars == expected_chars
    
    def test_cycling_wraps_around(self):
        """Test spinner wraps back to first character after last."""
        spinner = SpinnerAnimation()
        
        # Cycle through all 10 characters
        for i in range(10):
            spinner.update()
            time.sleep(0.11)
        
        # Next update should wrap back to first character
        char = spinner.update()
        assert char == '⠋'
        assert spinner.index == 1
    
    def test_multiple_cycles(self):
        """Test spinner can cycle multiple times correctly."""
        spinner = SpinnerAnimation()
        
        # Cycle through 25 characters (2.5 full cycles)
        chars = []
        for i in range(25):
            char = spinner.update()
            if char:
                chars.append(char)
            time.sleep(0.11)
        
        # Should have 25 characters
        assert len(chars) == 25
        
        # First 10 should match expected pattern
        expected = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        assert chars[:10] == expected
        
        # Second 10 should repeat the pattern
        assert chars[10:20] == expected
        
        # Last 5 should be first 5 of pattern
        assert chars[20:25] == expected[:5]
    
    def test_timing_precision(self):
        """Test update timing is accurate within reasonable tolerance."""
        spinner = SpinnerAnimation()
        
        # First update
        spinner.update()
        start_time = time.time()
        
        # Wait and update
        time.sleep(0.11)
        char = spinner.update()
        elapsed = time.time() - start_time
        
        # Should have returned a character
        assert char is not None
        
        # Elapsed time should be close to 110ms (within 20ms tolerance)
        assert 0.09 <= elapsed <= 0.15
    
    def test_last_update_time_tracking(self):
        """Test last_update time is properly tracked."""
        spinner = SpinnerAnimation()
        
        # Initial state
        assert spinner.last_update == 0
        
        # After first update
        before = time.time()
        spinner.update()
        after = time.time()
        
        # last_update should be between before and after
        assert before <= spinner.last_update <= after
    
    def test_rapid_updates(self):
        """Test rapid consecutive updates only return characters at intervals."""
        spinner = SpinnerAnimation()
        
        # First update should return character
        char1 = spinner.update()
        assert char1 is not None
        
        # Rapid updates should return None
        for _ in range(10):
            char = spinner.update()
            assert char is None
        
        # After waiting, should return next character
        time.sleep(0.11)
        char2 = spinner.update()
        assert char2 is not None
        assert char2 != char1
    
    def test_index_increments_correctly(self):
        """Test index increments with each successful update."""
        spinner = SpinnerAnimation()
        
        assert spinner.index == 0
        
        spinner.update()
        assert spinner.index == 1
        
        time.sleep(0.11)
        spinner.update()
        assert spinner.index == 2
        
        time.sleep(0.11)
        spinner.update()
        assert spinner.index == 3
    
    def test_index_modulo_wrapping(self):
        """Test index wraps using modulo operation."""
        spinner = SpinnerAnimation()
        
        # Manually set index to last position
        spinner.index = 9
        spinner.last_update = 0
        
        # Update should wrap to 0
        spinner.update()
        assert spinner.index == 0
        
        # Next update should be 1
        time.sleep(0.11)
        spinner.update()
        assert spinner.index == 1
