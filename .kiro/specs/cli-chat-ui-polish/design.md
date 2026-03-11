# Design Document: CLI Chat UI Polish

## Overview

This design adds ANSI green coloring to the interactive CLI chat labels and surfaces the time-to-first-token (TTFB) metric in the agent label. The changes are scoped to two files:

- `sales_agent_cli.py` — the `chat()` function's prompt and post-response output
- `streaming.py` — the `StreamingResponseHandler` spinner methods

All color output uses `click.style()`, which automatically detects terminal color support and falls back to plain text when ANSI is unavailable. No new dependencies are introduced.

## Architecture

The change is purely presentational. The existing control flow remains identical:

1. `chat()` loop reads input via `click.prompt()`
2. Message is sent over WebSocket
3. `StreamingResponseHandler.handle_stream()` processes the stream, showing a spinner during thinking and emitting response chunks
4. `chat()` prints the agent label (new) and optional verbose metrics, then loops

```mermaid
sequenceDiagram
    participant User
    participant chat() as chat() loop
    participant Handler as StreamingResponseHandler

    loop Each exchange
        chat()->>User: Green "You:" prompt (click.prompt with click.style)
        User->>chat(): typed message
        chat()->>Handler: handle_stream(ws)
        Handler->>Handler: _start_spinner() — green "⠋ Thinking..."
        Handler->>Handler: _update_spinner() — green spinner frames
        Handler->>Handler: _stop_spinner() — clear line
        Handler-->>chat(): (response_text, metrics)
        chat()->>User: Green "Agent[Xs]:" label on own line
        chat()->>User: Response text (already streamed by Handler)
        opt verbose mode
            chat()->>User: "TTFB: Xs | Total: Xs"
        end
        chat()->>User: Blank line separator
    end
```

## Components and Interfaces

### Modified: `chat()` in `sales_agent_cli.py`

**User Prompt Change**

Replace the plain `click.prompt("You", prompt_suffix=": ")` call with a styled version:

```python
styled_prompt = click.style("You", fg="green")
message = click.prompt(styled_prompt, prompt_suffix=": ")
```

`click.style()` returns the original string unchanged when the output stream lacks color support, satisfying the fallback requirement.

**Agent Label Change**

After `handle_stream()` returns, print a colored agent label on its own line before the response text. Since `handle_stream()` already streams response chunks to the terminal, the agent label must be printed *before* calling `handle_stream()` — but TTFB is only known *after* the stream completes. This creates a sequencing challenge.

**Resolution:** The response text is already streamed inline by `handle_stream()`. The agent label with TTFB must appear *after* the stream finishes (since TTFB isn't known until then). The current flow already streams text during `handle_stream()`, so the agent label will be printed after the handler returns, on a new line above a re-echo of the response. However, re-echoing the full response is wasteful.

**Chosen approach:** Modify `handle_stream()` to suppress inline `click.echo()` calls for response chunks. Instead, accumulate the response text and return it. The `chat()` function then:
1. Calls `handle_stream()` (which shows only the spinner, no response text)
2. Prints the green agent label with TTFB on its own line
3. Prints the accumulated response text
4. Optionally prints verbose metrics

This keeps the label placement correct and avoids duplicating output.

Alternatively, a simpler approach: keep the current streaming behavior (text appears as it arrives) and print the agent label *before* calling `handle_stream()` without TTFB, then print TTFB separately after. But this contradicts Requirement 2 which wants TTFB in the label itself.

**Final design decision:** Use the suppressed-echo approach. Add a `suppress_echo` parameter to `StreamingResponseHandler.__init__()` defaulting to `False` for backward compatibility. When `True`, response chunks are accumulated but not printed to the terminal. The `chat()` function sets `suppress_echo=True`.

```python
# In chat() after handle_stream returns:
ttfb = metrics.time_to_first_token
if ttfb is not None:
    label = click.style(f"Agent[{ttfb:.1f}s]", fg="green")
else:
    label = click.style("Agent", fg="green")
click.echo(f"{label}: ")
click.echo(response_text)
```

### Modified: `StreamingResponseHandler` in `streaming.py`

**Constructor Change**

Add `suppress_echo: bool = False` parameter:

```python
def __init__(self, verbosity: int = 0, suppress_echo: bool = False):
    self.verbosity = verbosity
    self.suppress_echo = suppress_echo
    self.metrics = PerformanceMetrics()
    self._spinner_running = False
    self._spinner_frame = 0
    self._state = _ThinkingState.WAITING
```

**`_process_chunk()` Change**

Guard all `click.echo(text, nl=False)` calls for response text behind `if not self.suppress_echo`. The thinking spinner output is unaffected — it always displays.

**Spinner Color Changes**

Apply `click.style()` to spinner text in `_start_spinner()` and `_update_spinner()`:

```python
def _start_spinner(self) -> None:
    self._spinner_running = True
    self._spinner_frame = 0
    text = click.style(f"{self.SPINNER_FRAMES[0]} Thinking...", fg="green")
    click.echo(f"\r{text}", nl=False)

def _update_spinner(self, thinking_text: str) -> None:
    if not self._spinner_running:
        return
    self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
    frame = self.SPINNER_FRAMES[self._spinner_frame]
    display_text = thinking_text.strip()
    if len(display_text) > 60:
        display_text = display_text[:57] + "..."
    text = click.style(f"{frame} Thinking: {display_text}", fg="green")
    click.echo(f"\r{text}    ", nl=False)
```

**`_stop_spinner()` Change**

Clear the spinner line using a carriage return and spaces to overwrite, then move to a new line. This ensures the colored spinner text is fully removed before the agent label appears:

```python
def _stop_spinner(self) -> None:
    if self._spinner_running:
        self._spinner_running = False
        click.echo("\r" + " " * 80 + "\r", nl=False)  # Clear spinner line
```

## Data Models

No new data models are introduced. The existing `PerformanceMetrics` dataclass is unchanged:

```python
@dataclass
class PerformanceMetrics:
    time_to_first_token: float | None = None
    total_duration: float | None = None
```

The `suppress_echo` flag is a simple boolean on `StreamingResponseHandler`, not a data model change.

### Helper Function: `format_agent_label`

A small pure function to format the agent label string, useful for testing:

```python
def format_agent_label(ttfb: float | None, use_color: bool = True) -> str:
    """Format the agent label with optional TTFB and color."""
    if ttfb is not None:
        label_text = f"Agent[{ttfb:.1f}s]"
    else:
        label_text = "Agent"
    if use_color:
        return click.style(label_text, fg="green") + ":"
    return label_text + ":"
```

This function lives in `streaming.py` alongside the handler, keeping formatting logic co-located.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Green styling applies ANSI escape codes

*For any* non-empty string, calling `click.style(text, fg="green")` should produce an output string that contains the ANSI green escape sequence (`\033[32m`) wrapping the original text, and the original text should be recoverable by stripping ANSI codes.

**Validates: Requirements 1.1, 5.1**

### Property 2: Color fallback returns plain text

*For any* non-empty string, calling `click.style(text, fg="green", color=False)` (or when the output stream lacks color support) should return the original string unchanged — no ANSI escape sequences present.

**Validates: Requirements 1.2, 2.3, 5.2**

### Property 3: Agent label TTFB formatting

*For any* float value `t >= 0`, `format_agent_label(t)` should produce a string matching the pattern `Agent[Xs]:` where `X` is `t` rounded to exactly one decimal place. When `t` is `None`, the output should be `Agent:`.

**Validates: Requirements 2.1, 2.2**

### Property 4: Agent label appears on its own line before response text

*For any* non-empty response text and any TTFB value (including None), the combined output of the agent label and response text should have the agent label on a line by itself, followed by the response text starting on the next line.

**Validates: Requirements 3.1**

### Property 5: Verbose mode shows both label and metrics without label duplication

*For any* metrics where `time_to_first_token` is not None and `verbosity >= 1`, the output should contain exactly one agent label line and one metrics line showing both TTFB and total duration. The agent label text (`Agent[Xs]:`) should appear exactly once.

**Validates: Requirements 4.1, 4.2**

## Error Handling

The color changes introduce no new error paths. `click.style()` is a pure string transformation that never raises exceptions. Specific considerations:

- **Terminal without color support:** `click.style()` auto-detects via `isatty()` and returns plain text. No explicit error handling needed.
- **Piped output:** When stdout is piped (e.g., `cli chat | tee log.txt`), Click strips ANSI codes automatically. The labels remain readable.
- **TTFB is None:** The `format_agent_label()` function handles `None` explicitly by omitting the bracket notation, producing `"Agent:"`.
- **Spinner clearing:** The `_stop_spinner()` method overwrites the spinner line with spaces. If the terminal width is less than 80 columns, some residual characters could remain. This is a cosmetic edge case, not a functional error.

## Testing Strategy

### Property-Based Testing

Use `hypothesis` as the property-based testing library (already available in the Python ecosystem, pairs well with pytest).

Each property test runs a minimum of 100 iterations. Tests are tagged with comments referencing the design property.

**Property tests to implement:**

1. **Feature: cli-chat-ui-polish, Property 1: Green styling applies ANSI escape codes**
   - Generate random non-empty strings via `hypothesis.strategies.text(min_size=1)`
   - Assert output of `click.style(text, fg="green")` contains `\033[32m` and the original text

2. **Feature: cli-chat-ui-polish, Property 2: Color fallback returns plain text**
   - Generate random non-empty strings
   - Assert `click.style(text, fg="green", color=False)` equals the original text

3. **Feature: cli-chat-ui-polish, Property 3: Agent label TTFB formatting**
   - Generate random non-negative floats via `hypothesis.strategies.floats(min_value=0, max_value=9999, allow_nan=False, allow_infinity=False)`
   - Assert `format_agent_label(ttfb, use_color=False)` matches `f"Agent[{ttfb:.1f}s]:"`
   - Also test with `None` input (edge case in unit test)

4. **Feature: cli-chat-ui-polish, Property 4: Agent label on its own line**
   - Generate random response strings and TTFB values
   - Assert the formatted output has the label on line 1 and response starting on line 2

5. **Feature: cli-chat-ui-polish, Property 5: Verbose mode dual display**
   - Generate random TTFB and total duration floats with verbosity >= 1
   - Assert output contains exactly one agent label and one metrics line

### Unit Tests

Unit tests cover specific examples and edge cases:

- `test_user_prompt_is_green`: Verify the "You" prompt string is styled green
- `test_agent_label_no_ttfb`: Verify `format_agent_label(None)` returns `"Agent:"`
- `test_agent_label_with_ttfb_rounding`: Verify `format_agent_label(1.749)` returns `"Agent[1.7s]:"`
- `test_spinner_start_is_green`: Verify `_start_spinner()` output contains green ANSI codes
- `test_spinner_clear_on_stop`: Verify `_stop_spinner()` clears the spinner line
- `test_blank_line_between_exchanges`: Verify a blank line separates agent response from next prompt
- `test_verbose_metrics_still_shown`: Verify verbose mode prints TTFB and total duration line
- `test_suppress_echo_prevents_inline_output`: Verify `suppress_echo=True` prevents response chunks from being printed during streaming

### Test Configuration

```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(text=st.text(min_size=1, max_size=200))
def test_green_style_contains_ansi(text):
    # Feature: cli-chat-ui-polish, Property 1: Green styling applies ANSI escape codes
    styled = click.style(text, fg="green")
    assert "\033[32m" in styled
    assert text in styled
```
