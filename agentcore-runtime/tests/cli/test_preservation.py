"""Preservation property tests — baseline behavior that must survive the fix.

These tests verify that existing CLI functionality works correctly on the
UNFIXED code and must continue to pass after the import fix is applied.

**Validates: Requirements 3.1, 3.2, 3.3**

Property 2: Preservation — CLI Functionality Unchanged for Module-Style Execution

_For any_ CLI invocation (commands, arguments, interactions), the fixed code
SHALL produce exactly the same behavior as the original code when imports
resolve successfully, preserving all command outputs, error handling, AWS
interactions, and streaming behavior.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from click.testing import CliRunner

# ── Path constants ──────────────────────────────────────────────────────────
AGENTCORE_RUNTIME_DIR = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Property 2.1: Version command preservation
# ---------------------------------------------------------------------------

class TestVersionPreservation:
    """Verify ``python -m cli version`` output is preserved.

    **Validates: Requirements 3.1, 3.2**
    """

    def test_module_version_command_output(self):
        """``python -m cli version`` must output 'sales-agent-cli 0.1.0'."""
        result = subprocess.run(
            [sys.executable, "-m", "cli", "version"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Exit code was {result.returncode}, stderr: {result.stderr}"
        assert result.stdout.strip() == "sales-agent-cli 0.1.0"

    def test_version_import_returns_expected_value(self):
        """``__version__`` from the cli package must be '0.1.0'."""
        from cli import __version__
        assert __version__ == "0.1.0"


# ---------------------------------------------------------------------------
# Property 2.2: Help command preservation
# ---------------------------------------------------------------------------

class TestHelpPreservation:
    """Verify ``python -m cli --help`` output is preserved.

    **Validates: Requirements 3.1**
    """

    EXPECTED_COMMANDS = {"chat", "invoke", "logs", "param", "status", "version"}

    def test_module_help_exits_zero(self):
        """``python -m cli --help`` must exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "cli", "--help"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_module_help_contains_description(self):
        """Help text must contain the CLI description."""
        result = subprocess.run(
            [sys.executable, "-m", "cli", "--help"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "Sales Agent CLI" in result.stdout

    def test_module_help_lists_all_commands(self):
        """Help text must list all expected commands."""
        result = subprocess.run(
            [sys.executable, "-m", "cli", "--help"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        for cmd in self.EXPECTED_COMMANDS:
            assert cmd in result.stdout, f"Command '{cmd}' missing from help output"

    def test_module_help_lists_options(self):
        """Help text must list --stack-name and --verbose options."""
        result = subprocess.run(
            [sys.executable, "-m", "cli", "--help"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "--stack-name" in result.stdout
        assert "--verbose" in result.stdout


# ---------------------------------------------------------------------------
# Property 2.3: Import preservation
# ---------------------------------------------------------------------------

class TestImportPreservation:
    """Verify key symbols are importable from the cli package.

    **Validates: Requirements 3.2, 3.3**
    """

    def test_version_importable(self):
        """``__version__`` must be importable from ``cli``."""
        from cli import __version__
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_streaming_handler_importable(self):
        """``StreamingResponseHandler`` must be importable from ``cli.streaming``."""
        from cli.streaming import StreamingResponseHandler
        handler = StreamingResponseHandler()
        assert handler is not None
        assert handler.verbosity == 0

    def test_cli_group_importable(self):
        """``cli`` Click group must be importable from ``cli.sales_agent_cli``."""
        from cli.sales_agent_cli import cli
        import click
        assert isinstance(cli, click.Group)

    def test_cli_group_has_expected_commands(self):
        """The ``cli`` Click group must contain all expected commands."""
        from cli.sales_agent_cli import cli
        expected = {"version", "invoke", "chat", "param", "logs", "status"}
        actual = set(cli.commands.keys())
        assert expected == actual, f"Expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Property 2.4: Property-based — CLI commands via CliRunner
# ---------------------------------------------------------------------------

VALID_COMMANDS = ["version", "--help"]


class TestCLICommandsProperty:
    """Property-based: for all valid CLI commands, output matches baseline.

    **Validates: Requirements 3.1, 3.2**
    """

    @given(cmd=st.sampled_from(VALID_COMMANDS))
    @settings(max_examples=10)
    def test_valid_commands_exit_zero(self, cmd):
        """For all valid CLI commands, exit code must be 0."""
        from cli.sales_agent_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [cmd])
        assert result.exit_code == 0, (
            f"Command '{cmd}' exited with {result.exit_code}: {result.output}"
        )

    @given(cmd=st.sampled_from(VALID_COMMANDS))
    @settings(max_examples=10)
    def test_valid_commands_produce_output(self, cmd):
        """For all valid CLI commands, output must be non-empty."""
        from cli.sales_agent_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [cmd])
        assert len(result.output.strip()) > 0, (
            f"Command '{cmd}' produced empty output"
        )

    def test_version_command_exact_output(self):
        """The version command must produce exactly 'sales-agent-cli 0.1.0'."""
        from cli.sales_agent_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert result.output.strip() == "sales-agent-cli 0.1.0"

    def test_help_command_contains_all_commands(self):
        """The --help output must list all expected commands."""
        from cli.sales_agent_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ["chat", "invoke", "logs", "param", "status", "version"]:
            assert cmd in result.output
