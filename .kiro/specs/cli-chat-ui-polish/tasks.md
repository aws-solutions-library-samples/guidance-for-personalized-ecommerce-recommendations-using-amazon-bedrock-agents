# Implementation Plan: CLI Chat UI Polish

## Overview

Add ANSI green coloring to the CLI chat labels (user prompt, agent label, thinking spinner) and surface TTFB in the agent label. Changes are scoped to `streaming.py` (handler + helper) and `sales_agent_cli.py` (chat loop). All color output uses `click.style()` for automatic terminal fallback.

## Tasks

- [x] 1. Add `suppress_echo` parameter and `format_agent_label` helper to `StreamingResponseHandler`
  - [x] 1.1 Add `suppress_echo` parameter to `StreamingResponseHandler.__init__()` defaulting to `False`
    - Add `self.suppress_echo = suppress_echo` to the constructor
    - Guard all `click.echo(text, nl=False)` calls for response text in `_process_chunk()` behind `if not self.suppress_echo`
    - Accumulated `response_text` must still be built regardless of `suppress_echo`
    - _Requirements: 2.1, 3.1_

  - [x] 1.2 Add `format_agent_label()` helper function in `streaming.py`
    - Implement as a module-level pure function: `format_agent_label(ttfb: float | None, use_color: bool = True) -> str`
    - When `ttfb` is not None, format as `Agent[{ttfb:.1f}s]:` with green styling
    - When `ttfb` is None, format as `Agent:` with green styling
    - When `use_color` is False, return plain text without ANSI codes
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 1.3 Write property test for `format_agent_label` TTFB formatting
    - **Property 3: Agent label TTFB formatting**
    - Generate non-negative floats via `hypothesis.strategies.floats(min_value=0, max_value=9999, allow_nan=False, allow_infinity=False)`
    - Assert `format_agent_label(ttfb, use_color=False)` matches `f"Agent[{ttfb:.1f}s]:"`
    - Also test `format_agent_label(None, use_color=False)` returns `"Agent:"`
    - **Validates: Requirements 2.1, 2.2**

- [x] 2. Color the thinking spinner
  - [x] 2.1 Apply green styling to `_start_spinner()` and `_update_spinner()` in `streaming.py`
    - Wrap spinner text with `click.style(..., fg="green")` in `_start_spinner()`
    - Wrap spinner text with `click.style(..., fg="green")` in `_update_spinner()`
    - _Requirements: 5.1, 5.2_

  - [x] 2.2 Clear spinner line properly in `_stop_spinner()`
    - Replace `click.echo("")` with `click.echo("\r" + " " * 80 + "\r", nl=False)` to overwrite the colored spinner text
    - Ensures no residual ANSI-colored text remains before the agent label prints
    - _Requirements: 5.3_

  - [ ]* 2.3 Write property test for green styling ANSI escape codes
    - **Property 1: Green styling applies ANSI escape codes**
    - Generate random non-empty strings via `hypothesis.strategies.text(min_size=1, max_size=200)`
    - Assert `click.style(text, fg="green")` contains `\033[32m` and the original text
    - **Validates: Requirements 1.1, 5.1**

  - [ ]* 2.4 Write property test for color fallback
    - **Property 2: Color fallback returns plain text**
    - Generate random non-empty strings
    - Assert `click.style(text, fg="green", color=False)` equals the original text unchanged
    - **Validates: Requirements 1.2, 2.3, 5.2**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update `chat()` loop in `sales_agent_cli.py` for colored prompt and agent label
  - [x] 4.1 Color the "You:" user prompt green
    - Replace `click.prompt("You", prompt_suffix=": ")` with `click.prompt(click.style("You", fg="green"), prompt_suffix=": ")`
    - _Requirements: 1.1, 1.2_

  - [x] 4.2 Use `suppress_echo=True` and print agent label with TTFB after `handle_stream()` returns
    - In the `_send()` coroutine, pass `suppress_echo=True` to `StreamingResponseHandler`
    - After `handle_stream()` returns, use `format_agent_label()` to build the label
    - Print the agent label on its own line via `click.echo(label)`
    - Print the accumulated `response_text` via `click.echo(response_text)`
    - Keep the existing verbose metrics line (`TTFB: Xs | Total: Xs`) when `verbosity >= 1`
    - Keep the blank line `click.echo("")` between exchanges
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 4.1, 4.2_

  - [ ]* 4.3 Write property test for agent label appearing on its own line
    - **Property 4: Agent label appears on its own line before response text**
    - Generate random response strings and TTFB values
    - Assert formatted output has label on line 1 and response starting on line 2
    - **Validates: Requirements 3.1**

  - [ ]* 4.4 Write property test for verbose mode dual display
    - **Property 5: Verbose mode shows both label and metrics without label duplication**
    - Generate random TTFB and total duration floats with verbosity >= 1
    - Assert output contains exactly one agent label line and one metrics line
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 4.5 Write unit tests for chat UI polish
    - Test `format_agent_label(None)` returns `"Agent:"`
    - Test `format_agent_label(1.749, use_color=False)` returns `"Agent[1.7s]:"`
    - Test `suppress_echo=True` prevents inline `click.echo` during streaming
    - Test blank line between exchanges is preserved
    - _Requirements: 2.2, 3.2_

- [x] 5. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All color output uses `click.style(fg="green")` which auto-falls back to plain text on non-ANSI terminals
- No new dependencies are introduced; `hypothesis` is used for property-based tests
- The `suppress_echo` approach avoids duplicating streamed output while allowing the agent label with TTFB to appear before the response text
