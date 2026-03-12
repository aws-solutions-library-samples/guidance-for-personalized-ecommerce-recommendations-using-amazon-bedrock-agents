"""Bug condition exploration test for absolute import failure.

This test verifies that the imports in cli/sales_agent_cli.py and
cli/__main__.py resolve correctly when the package is imported properly.

The original bug condition was: absolute imports like
``from cli import __version__`` fail with ``ModuleNotFoundError`` when
the ``cli`` package parent directory is not on ``sys.path``.

The fix converts absolute imports to relative imports (``from . import __version__``),
which resolve correctly when the modules are loaded as part of the ``cli`` package.

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**

EXPECTED BEHAVIOR (after fix):
- Imports resolve without ModuleNotFoundError
- __version__ is accessible
- StreamingResponseHandler is accessible

On UNFIXED code these tests FAIL — which is the correct outcome for a bug
condition exploration test: failure proves the bug exists.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Resolve paths
CLI_PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent / "cli"
AGENTCORE_RUNTIME_DIR = CLI_PACKAGE_DIR.parent


def _run_module_import(module_path: str):
    """Import a cli submodule via ``python -m`` or importlib in a subprocess.

    This tests that relative imports resolve correctly when the module is
    loaded as part of the ``cli`` package — the execution context that the
    fix targets.
    """
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    return subprocess.run(
        [sys.executable, "-m", module_path],
        cwd=str(AGENTCORE_RUNTIME_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _run_import_check(import_statement: str):
    """Run a Python import statement in a subprocess with agent-core
    as the working directory and on sys.path, simulating package-aware execution.

    This verifies that relative imports inside the cli package resolve correctly.
    """
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(AGENTCORE_RUNTIME_DIR)!r}); "
                f"{import_statement}"
            ),
        ],
        cwd=str(AGENTCORE_RUNTIME_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestBugConditionSalesAgentCLI:
    """Verify that sales_agent_cli.py imports resolve correctly in package context.

    On unfixed code these FAIL with ModuleNotFoundError (proving the bug).
    After the fix, relative imports should resolve and the CLI should start.
    """

    def test_sales_agent_cli_module_execution_succeeds(self):
        """Running ``python -m cli`` with --help should not crash with
        ModuleNotFoundError or ImportError.

        **Validates: Requirements 1.1, 1.2, 2.1, 2.2**
        """
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, "-m", "cli", "--help"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Module execution of cli failed.\n"
            f"stderr: {result.stderr}"
        )
        assert "ModuleNotFoundError" not in result.stderr
        assert "ImportError" not in result.stderr

    def test_version_accessible_via_package_import(self):
        """Importing cli.sales_agent_cli as a package should successfully
        resolve __version__ (used by the ``version`` command).

        **Validates: Requirements 2.1, 2.2**
        """
        result = _run_import_check(
            "from cli.sales_agent_cli import cli; print('OK')"
        )

        assert result.returncode == 0, (
            f"Importing cli.sales_agent_cli as package failed.\n"
            f"stderr: {result.stderr}"
        )
        assert "ModuleNotFoundError" not in result.stderr
        assert "ImportError" not in result.stderr
        assert "OK" in result.stdout

    def test_streaming_handler_accessible_via_package_import(self):
        """StreamingResponseHandler should be importable when loading
        sales_agent_cli as part of the cli package.

        **Validates: Requirements 2.2**
        """
        result = _run_import_check(
            "from cli.streaming import StreamingResponseHandler; print('OK')"
        )

        assert result.returncode == 0, (
            f"Importing StreamingResponseHandler from cli.streaming failed.\n"
            f"stderr: {result.stderr}"
        )
        assert "ModuleNotFoundError" not in result.stderr
        assert "ImportError" not in result.stderr
        assert "OK" in result.stdout


class TestBugConditionMainModule:
    """Verify that __main__.py imports resolve correctly in package context.

    On unfixed code these FAIL with ModuleNotFoundError (proving the bug).
    After the fix, relative imports should resolve successfully.
    """

    def test_main_module_execution_succeeds(self):
        """Running ``python -m cli --help`` should not crash with
        ModuleNotFoundError or ImportError.

        **Validates: Requirements 1.3, 2.3**
        """
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, "-m", "cli", "--help"],
            cwd=str(AGENTCORE_RUNTIME_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert "ModuleNotFoundError" not in result.stderr, (
            f"Module execution of cli failed with ModuleNotFoundError.\n"
            f"stderr: {result.stderr}"
        )
        assert "ImportError" not in result.stderr, (
            f"Module execution of cli failed with ImportError.\n"
            f"stderr: {result.stderr}"
        )
        assert result.returncode == 0, (
            f"cli module exited with non-zero code.\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )
