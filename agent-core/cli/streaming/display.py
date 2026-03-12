"""
Terminal display components for streaming chat responses.

This module provides classes for managing terminal output during streaming
responses, including animated spinners and verbosity-controlled display.
"""

import time
from typing import Optional


class SpinnerAnimation:
    """
    Animated spinner for thinking indicator.
    
    Cycles through Braille pattern characters at 10 FPS (100ms interval)
    to provide visual feedback during agent processing.
    """
    
    CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    UPDATE_INTERVAL = 0.1  # 100ms = 10 FPS
    
    def __init__(self):
        """Initialize spinner with starting state."""
        self.index = 0
        self.last_update = 0
    
    def update(self) -> Optional[str]:
        """
        Return next spinner character if update interval has elapsed.
        
        Returns:
            Next spinner character if 100ms has passed since last update,
            None otherwise.
        """
        current_time = time.time()
        
        # Check if enough time has passed since last update
        if current_time - self.last_update >= self.UPDATE_INTERVAL:
            # Get current character
            char = self.CHARS[self.index]
            
            # Advance to next character (cycle back to 0 after last)
            self.index = (self.index + 1) % len(self.CHARS)
            
            # Update last update time
            self.last_update = current_time
            
            return char
        
        return None


class TerminalDisplay:
    """
    Terminal output manager with verbosity control.
    
    Manages all terminal output during streaming responses, including
    thinking indicators, agent responses, raw events, and performance metrics.
    Respects verbosity levels to control what information is displayed.
    
    Verbosity Levels:
        0: Normal user output (thinking spinner + agent response)
        1: + Thinking content + Performance metrics summary
        2: + All raw streaming events + Detailed timing
    """
    
    # ANSI color codes for terminal output
    COLOR_GRAY = '\033[90m'
    COLOR_CYAN = '\033[36m'
    COLOR_GREEN = '\033[32m'
    COLOR_YELLOW = '\033[33m'
    COLOR_RESET = '\033[0m'
    
    def __init__(self, verbosity: int = 0):
        """
        Initialize terminal display.
        
        Args:
            verbosity: Output verbosity level (0, 1, or 2)
        """
        self.verbosity = verbosity
        self.thinking_shown = False
        self.agent_label_shown = False
        self.spinner = SpinnerAnimation()
        self.last_spinner_char = None
    
    def show_thinking(self) -> None:
        """
        Display thinking indicator with animated spinner.
        
        Shows "Thinking: ⠋" with animated spinner that updates at 10 FPS.
        Only displays once per response.
        """
        if not self.thinking_shown:
            # Show initial thinking message
            print(f"{self.COLOR_GRAY}Thinking: ", end='', flush=True)
            self.thinking_shown = True
            self.last_spinner_char = None
        
        # Update spinner animation
        spinner_char = self.spinner.update()
        if spinner_char:
            # Clear previous spinner character and show new one
            if self.last_spinner_char:
                print('\b', end='', flush=True)  # Backspace
            print(spinner_char, end='', flush=True)
            self.last_spinner_char = spinner_char
    
    def show_thinking_content(self, content: str) -> None:
        """
        Display thinking content in verbose mode.
        
        Only displays if verbosity >= 1. Shows the agent's internal
        reasoning process in a distinct color.
        
        Args:
            content: The thinking content to display
        """
        if self.verbosity >= 1:
            # Clear thinking line if shown
            if self.thinking_shown and not self.agent_label_shown:
                print(f'\r{" " * 50}\r', end='', flush=True)
            
            # Display thinking content in gray
            print(f"{self.COLOR_GRAY}[Thinking] {content}{self.COLOR_RESET}")
    
    def show_agent_response(self, text: str, elapsed_time: Optional[float] = None) -> None:
        """
        Display agent response with timing information.
        
        Shows "Agent[X.Xs]: " label on first call, then streams response text.
        Clears the thinking line before showing the response.
        
        Args:
            text: Response text to display
            elapsed_time: Time elapsed since request started (seconds)
        """
        # Clear thinking line and show agent label on first response
        if not self.agent_label_shown:
            # Clear the thinking line
            if self.thinking_shown:
                print(f'\r{" " * 50}\r', end='', flush=True)
            
            # Show agent label with timing
            if elapsed_time is not None:
                print(f"{self.COLOR_GREEN}Agent[{elapsed_time:.1f}s]:{self.COLOR_RESET} ", end='', flush=True)
            else:
                print(f"{self.COLOR_GREEN}Agent:{self.COLOR_RESET} ", end='', flush=True)
            
            self.agent_label_shown = True
        
        # Display response text
        print(text, end='', flush=True)
    
    def show_raw_event(self, event: dict) -> None:
        """
        Display raw streaming event in debug mode.
        
        Only displays if verbosity >= 2. Shows the complete event
        structure for debugging purposes.
        
        Args:
            event: The raw event dictionary to display
        """
        if self.verbosity >= 2:
            # Display raw event in yellow
            print(f"{self.COLOR_YELLOW}[RAW EVENT] {event}{self.COLOR_RESET}")
    
    def show_metrics(self, metrics_summary: str) -> None:
        """
        Display performance metrics in verbose mode.
        
        Only displays if verbosity >= 1. Shows timing information
        including connection time, TTFB, and total response time.
        
        Args:
            metrics_summary: Formatted metrics string (e.g., "Connection: 32ms, TTFB: 44ms, Total: 1045ms")
        """
        if self.verbosity >= 1:
            print(f"\n{self.COLOR_CYAN}[Metrics] {metrics_summary}{self.COLOR_RESET}")
    
    def finish_response(self) -> None:
        """
        Finish the response output.
        
        Adds a newline after the response text to prepare for next output.
        """
        if self.agent_label_shown:
            print()  # Newline after response
    
    def reset(self) -> None:
        """
        Reset display state for next response.
        
        Clears all state flags to prepare for displaying a new response.
        """
        self.thinking_shown = False
        self.agent_label_shown = False
        self.last_spinner_char = None
        self.spinner = SpinnerAnimation()
