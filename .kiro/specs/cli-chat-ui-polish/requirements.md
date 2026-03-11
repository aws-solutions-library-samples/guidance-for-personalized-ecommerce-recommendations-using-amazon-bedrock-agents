# Requirements Document

## Introduction

Polish the interactive CLI chat interface for the Sales Agent CLI tool. The chat loop currently displays a plain "You:" prompt with no color and streams agent responses without a labeled prefix or timing information. This feature adds colored labels for both user and agent turns, and surfaces the time-to-first-token (TTFB) metric directly in the agent label so operators can gauge responsiveness at a glance without enabling verbose mode.

## Glossary

- **Chat_Loop**: The interactive `while True` loop in the `chat()` command that alternates between reading user input and streaming agent responses.
- **User_Prompt**: The "You:" label displayed before the user types a message.
- **Agent_Label**: The "Agent[Xs]:" label displayed before the agent's streamed response, where X is the TTFB value.
- **TTFB**: Time-to-first-token — the elapsed seconds from sending the user message until the first non-thinking response token arrives from the WebSocket stream.
- **StreamingResponseHandler**: The class in `streaming.py` that processes WebSocket messages, manages the thinking spinner, and emits response text to the terminal.

## Requirements

### Requirement 1: Colored User Prompt

**User Story:** As a CLI operator, I want the "You:" input prompt to be displayed in green, so that I can visually distinguish my input from agent output.

#### Acceptance Criteria

1. THE Chat_Loop SHALL display the User_Prompt text "You:" in ANSI green color.
2. WHEN the terminal does not support ANSI colors, THE Chat_Loop SHALL fall back to displaying the User_Prompt without color formatting.

### Requirement 2: Colored Agent Label with TTFB

**User Story:** As a CLI operator, I want to see a green "Agent[Xs]:" label before every agent response showing the time-to-first-token, so that I can monitor response latency without enabling verbose mode.

#### Acceptance Criteria

1. WHEN the StreamingResponseHandler finishes streaming a response and TTFB is available, THE Chat_Loop SHALL print an Agent_Label in the format "Agent[{ttfb}s]:" in ANSI green color before the response text, where {ttfb} is the TTFB value rounded to one decimal place.
2. WHEN the StreamingResponseHandler finishes streaming a response and TTFB is not available, THE Chat_Loop SHALL print an Agent_Label in the format "Agent:" in ANSI green color before the response text.
3. WHEN the terminal does not support ANSI colors, THE Chat_Loop SHALL fall back to displaying the Agent_Label without color formatting.

### Requirement 3: Agent Label Placement

**User Story:** As a CLI operator, I want the agent label to appear on its own line directly before the agent's response text, so that the chat transcript is easy to read.

#### Acceptance Criteria

1. THE Chat_Loop SHALL print the Agent_Label on a separate line before the streamed response text begins.
2. THE Chat_Loop SHALL print one blank line between the end of an agent response and the next User_Prompt, preserving visual separation between exchanges.

### Requirement 4: Verbose TTFB Display Preserved

**User Story:** As a CLI operator using verbose mode, I want to continue seeing the detailed TTFB and total duration line, so that I retain access to full performance metrics.

#### Acceptance Criteria

1. WHILE verbosity is set to 1 or higher, THE Chat_Loop SHALL continue to print the detailed metrics line showing TTFB and total duration after the agent response.
2. THE Chat_Loop SHALL display both the Agent_Label TTFB and the verbose metrics line when verbose mode is enabled, without duplication of the label itself.

### Requirement 5: Colored Thinking Spinner Label

**User Story:** As a CLI operator, I want the "Thinking..." spinner text to be displayed in green, so that it is visually consistent with the other colored labels in the chat interface.

#### Acceptance Criteria

1. WHILE the StreamingResponseHandler is waiting for the first response token, THE StreamingResponseHandler SHALL display the thinking spinner text (e.g., "⠋ Thinking...") in ANSI green color.
2. WHEN the terminal does not support ANSI colors, THE StreamingResponseHandler SHALL fall back to displaying the thinking spinner text without color formatting.
3. WHEN the first response token arrives, THE StreamingResponseHandler SHALL clear the colored thinking spinner text before printing the Agent_Label and response.
