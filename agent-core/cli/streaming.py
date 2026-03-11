"""Streaming response handler for WebSocket-based agent communication."""

import asyncio
import time
import json
import click
from dataclasses import dataclass
from enum import Enum


@dataclass
class PerformanceMetrics:
    """Tracks timing data for a single agent invocation."""

    time_to_first_token: float | None = None
    total_duration: float | None = None


class _ThinkingState(Enum):
    """State machine states for thinking tag parsing."""

    WAITING = "waiting"
    THINKING = "thinking"
    RESPONDING = "responding"


class StreamingResponseHandler:
    """Processes streamed WebSocket responses with thinking spinner and metrics."""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, verbosity: int = 0):
        self.verbosity = verbosity
        self.metrics = PerformanceMetrics()
        self._spinner_running = False
        self._spinner_frame = 0
        self._state = _ThinkingState.WAITING

    async def handle_stream(self, websocket) -> tuple[str, PerformanceMetrics]:
        """
        Process the WebSocket stream.

        1. Start thinking spinner
        2. On <thinking> content: show alongside spinner
        3. On first non-thinking chunk: stop spinner, start printing
        4. Record TTFB and total duration
        5. Return (full_response_text, metrics)

        WebSocket messages are JSON with either:
        - "result" key (final response)
        - "chunk" key (streaming chunk)
        - "error" key (error message)
        """
        response_text = ""
        start_time = time.monotonic()
        self._state = _ThinkingState.WAITING
        self._start_spinner()

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except (json.JSONDecodeError, TypeError):
                    continue

                # Handle error messages
                if "error" in message:
                    self._stop_spinner()
                    error_msg = message["error"]
                    click.echo(f"\nError: {error_msg}", err=True)
                    self.metrics.total_duration = time.monotonic() - start_time
                    return response_text, self.metrics

                # Extract text from chunk or result
                text = message.get("chunk") or message.get("result", "")
                if not text:
                    continue

                # Process through the thinking state machine
                response_text = self._process_chunk(
                    text, response_text, start_time
                )

                # If this was a "result" message, stream is done
                if "result" in message:
                    break

        except Exception as exc:
            self._stop_spinner()
            click.echo(f"\nStream error: {exc}", err=True)
            self.metrics.total_duration = time.monotonic() - start_time
            return response_text, self.metrics

        self._stop_spinner()
        self.metrics.total_duration = time.monotonic() - start_time
        if self._state == _ThinkingState.RESPONDING:
            click.echo("")  # Final newline after streamed response
        return response_text, self.metrics

    def _process_chunk(
        self, text: str, response_text: str, start_time: float
    ) -> str:
        """Process a chunk through the thinking tag state machine."""
        if self._state == _ThinkingState.WAITING:
            if "<thinking>" in text:
                self._state = _ThinkingState.THINKING
                # Extract thinking content after the tag
                thinking_content = text.split("<thinking>", 1)[1]
                if "</thinking>" in thinking_content:
                    thinking_content = thinking_content.split(
                        "</thinking>", 1
                    )[0]
                    self._update_spinner(thinking_content)
                    self._state = _ThinkingState.RESPONDING
                    self._stop_spinner()
                    # Check for response text after </thinking>
                    after = text.split("</thinking>", 1)[1]
                    if after:
                        if self.metrics.time_to_first_token is None:
                            self.metrics.time_to_first_token = (
                                time.monotonic() - start_time
                            )
                        click.echo(after, nl=False)
                        response_text += after
                else:
                    self._update_spinner(thinking_content)
            else:
                # No thinking tags — go straight to responding
                self._state = _ThinkingState.RESPONDING
                self._stop_spinner()
                if self.metrics.time_to_first_token is None:
                    self.metrics.time_to_first_token = (
                        time.monotonic() - start_time
                    )
                click.echo(text, nl=False)
                response_text += text

        elif self._state == _ThinkingState.THINKING:
            if "</thinking>" in text:
                thinking_content = text.split("</thinking>", 1)[0]
                if thinking_content:
                    self._update_spinner(thinking_content)
                self._state = _ThinkingState.RESPONDING
                self._stop_spinner()
                # Check for response text after </thinking>
                after = text.split("</thinking>", 1)[1]
                if after:
                    if self.metrics.time_to_first_token is None:
                        self.metrics.time_to_first_token = (
                            time.monotonic() - start_time
                        )
                    click.echo(after, nl=False)
                    response_text += after
            else:
                self._update_spinner(text)

        elif self._state == _ThinkingState.RESPONDING:
            if self.metrics.time_to_first_token is None:
                self.metrics.time_to_first_token = (
                    time.monotonic() - start_time
                )
            click.echo(text, nl=False)
            response_text += text

        return response_text

    def _start_spinner(self) -> None:
        """Start the animated thinking spinner."""
        self._spinner_running = True
        self._spinner_frame = 0
        click.echo(
            f"\r{self.SPINNER_FRAMES[0]} Thinking...", nl=False
        )

    def _update_spinner(self, thinking_text: str) -> None:
        """Update spinner with thinking tag content."""
        if not self._spinner_running:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(
            self.SPINNER_FRAMES
        )
        frame = self.SPINNER_FRAMES[self._spinner_frame]
        # Truncate long thinking text to fit terminal
        display_text = thinking_text.strip()
        if len(display_text) > 60:
            display_text = display_text[:57] + "..."
        click.echo(f"\r{frame} Thinking: {display_text}    ", nl=False)

    def _stop_spinner(self) -> None:
        """Stop spinner when first response chunk arrives.

        Leaves the spinner line visible, response starts on new line.
        """
        if self._spinner_running:
            self._spinner_running = False
            click.echo("")  # Move to new line, leaving spinner visible
