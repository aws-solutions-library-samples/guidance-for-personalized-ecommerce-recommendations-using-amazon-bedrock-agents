"""Unit tests for the Sales Agent CLI commands."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from cli import __version__
from cli.sales_agent_cli import cli, _get_cli, SalesAgentCLI


class TestVersionCommand:
    """Tests for the version command."""

    def test_version_outputs_correct_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_output_format(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.output.strip() == f"sales-agent-cli {__version__}"


class TestCLIGroup:
    """Tests for the top-level CLI group."""

    def test_cli_help_output(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Sales Agent CLI" in result.output
        assert "--stack-name" in result.output
        assert "--verbose" in result.output


class TestGetCLI:
    """Tests for the _get_cli helper."""

    def test_get_cli_raises_error_when_no_stack_name(self):
        runner = CliRunner()
        # Invoke a command that calls _get_cli without providing stack name
        # Use 'param list' since it triggers _get_cli via the param group
        result = runner.invoke(cli, ["param", "list"])
        assert result.exit_code != 0
        assert "Stack name is required" in result.output

    @patch("cli.sales_agent_cli.SalesAgentCLI.validate_credentials")
    @patch("cli.sales_agent_cli.SalesAgentCLI.validate_stack")
    def test_get_cli_creates_instance_with_stack_name(
        self, mock_validate_stack, mock_validate_creds
    ):
        mock_validate_stack.return_value = {}
        mock_validate_creds.return_value = {"Arn": "arn:aws:iam::123:user/test"}
        runner = CliRunner()
        result = runner.invoke(cli, ["--stack-name", "TestStack", "param", "list"])
        mock_validate_creds.assert_called_once()
        mock_validate_stack.assert_called_once()
