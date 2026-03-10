#!/usr/bin/env python3
"""Interactive Chat CLI for the AgentCore Sales Agent.

Usage:
    python chat_cli.py [--endpoint <url>] [--user-id <id>]

Reads the agent endpoint from --endpoint arg or AGENTCORE_ENDPOINT env var.
CLI arg takes precedence over the env var.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def resolve_endpoint(cli_arg: str | None) -> str | None:
    """Resolve the endpoint from CLI arg or environment variable.

    CLI argument takes precedence over the AGENTCORE_ENDPOINT env var.
    """
    if cli_arg:
        return cli_arg
    return os.environ.get("AGENTCORE_ENDPOINT")


def build_payload(message: str, user_id: str | None = None) -> dict:
    """Build the JSON payload for the agent endpoint.

    Always includes 'prompt'. Includes 'user_id' only when provided.
    """
    payload = {"prompt": message}
    if user_id is not None:
        payload["user_id"] = user_id
    return payload


def send_message(endpoint: str, payload: dict) -> str:
    """Send a message to the agent endpoint via HTTP POST and return the response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("result", str(body))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Interactive chat with the AgentCore Sales Agent."
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="AgentCore Runtime agent endpoint URL. "
        "Falls back to AGENTCORE_ENDPOINT env var.",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Optional user ID to include in the payload for personalized interactions.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the interactive chat REPL."""
    args = parse_args(argv)

    endpoint = resolve_endpoint(args.endpoint)
    if not endpoint:
        print(
            "Error: No endpoint provided.\n"
            "Usage: python chat_cli.py --endpoint <url>\n"
            "   or set the AGENTCORE_ENDPOINT environment variable."
        )
        sys.exit(1)

    print("Welcome to the AgentCore Sales Agent Chat!")
    print("Type your message and press Enter. Type 'exit' or 'quit' to end the session.\n")

    while True:
        try:
            message = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        stripped = message.strip().lower()
        if stripped in ("exit", "quit"):
            print("Goodbye! Thanks for chatting.")
            break

        if not message.strip():
            continue

        payload = build_payload(message, args.user_id)

        try:
            response = send_message(endpoint, payload)
            print(f"Agent: {response}\n")
        except urllib.error.URLError as exc:
            print(f"Connection error: {exc.reason}")
            print("Please check the endpoint and try again.\n")
        except Exception as exc:
            print(f"Error: {exc}")
            print("Something went wrong. Please try again.\n")


if __name__ == "__main__":
    main()
