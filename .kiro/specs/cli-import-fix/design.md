# CLI Import Fix Bugfix Design

## Overview

The CLI package (`agentcore-runtime/cli/`) uses absolute imports (`from cli import ...`, `from cli.streaming import ...`, `from cli.sales_agent_cli import ...`) that fail with `ModuleNotFoundError` when the scripts are executed directly rather than as a module. The fix converts these to relative imports (`from . import ...`, `from .streaming import ...`, `from .sales_agent_cli import ...`) so that intra-package references resolve correctly regardless of execution context.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — when Python files inside the `cli` package use absolute imports referencing `cli.*` and the package directory is not on `sys.path`
- **Property (P)**: The desired behavior — all intra-package imports resolve successfully and the CLI starts without `ModuleNotFoundError`
- **Preservation**: Existing CLI functionality (commands, version display, streaming, parameter management, logging) must remain unchanged by the fix
- **`sales_agent_cli.py`**: The main CLI entry point in `agentcore-runtime/cli/` that defines all Click commands
- **`__main__.py`**: The module entry point in `agentcore-runtime/cli/` that enables `python -m cli` execution
- **`__version__`**: The version string defined in `agentcore-runtime/cli/__init__.py`
- **`StreamingResponseHandler`**: The class in `agentcore-runtime/cli/streaming.py` used by `invoke` and `chat` commands

## Bug Details

### Bug Condition

The bug manifests when a user runs `sales_agent_cli.py` or `__main__.py` directly (e.g., `python3 sales_agent_cli.py`) rather than as a module (`python -m cli`). The Python interpreter does not add the parent directory of `cli/` to `sys.path`, so absolute imports like `from cli import __version__` fail because the `cli` package cannot be found.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type PythonExecutionContext
  OUTPUT: boolean

  RETURN input.file IN ['cli/sales_agent_cli.py', 'cli/__main__.py']
         AND input.importStyle == 'absolute'  -- e.g., 'from cli import ...'
         AND NOT 'cli' IN sys.path_packages   -- parent dir not on sys.path
END FUNCTION
```

### Examples

- Running `python3 agentcore-runtime/cli/sales_agent_cli.py --stack-name MyStack` crashes with `ModuleNotFoundError: No module named 'cli'` at line 16 (`from cli import __version__`). Expected: CLI starts normally.
- Running `python3 agentcore-runtime/cli/__main__.py` crashes with `ModuleNotFoundError: No module named 'cli'` at line 2 (`from cli.sales_agent_cli import cli`). Expected: CLI starts normally.
- Running `cd agentcore-runtime && python -m cli version` works correctly today because `-m` adds the parent directory to `sys.path`. Expected: continues to work after fix.
- Running `python3 sales_agent_cli.py` from within the `cli/` directory crashes. Expected: CLI starts normally with relative imports.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All CLI commands (`version`, `invoke`, `chat`, `param set/get/list`, `logs`, `status`) must continue to function identically
- `python -m cli` execution from `agentcore-runtime/` must continue to work
- The `version` command must continue to display the correct version string from `__version__`
- The `invoke` and `chat` commands must continue to use `StreamingResponseHandler` without errors
- All existing tests in `tests/cli/` must continue to pass

**Scope:**
All inputs that do NOT involve the import resolution of `cli.*` absolute imports should be completely unaffected by this fix. This includes:
- All CLI command logic and argument parsing
- AWS client interactions (STS, CloudFormation, SSM, CloudWatch, ECS)
- WebSocket communication and streaming response handling
- Log file writing and time expression parsing

## Hypothesized Root Cause

Based on the bug description, the root cause is straightforward:

1. **Absolute imports in `sales_agent_cli.py`**: Lines 16-17 use `from cli import __version__` and `from cli.streaming import StreamingResponseHandler`. These are absolute imports that require the `cli` package to be discoverable on `sys.path`. When running the script directly, Python sets `__name__` to `"__main__"` and does not treat the containing directory as a package, so `cli` is not importable.

2. **Absolute import in `__main__.py`**: Line 2 uses `from cli.sales_agent_cli import cli`. Same issue — when executed directly, the `cli` package is not on `sys.path`.

3. **Why `python -m cli` works**: When using `-m`, Python adds the current working directory to `sys.path` and treats `cli` as a package, making absolute imports resolve. This masks the bug during module-style execution.

The fix is mechanical: convert the three absolute imports to relative imports. No logic changes are needed.

## Correctness Properties

Property 1: Bug Condition - Relative Imports Resolve Successfully

_For any_ execution context where `sales_agent_cli.py` or `__main__.py` is loaded (whether directly or as a module), the fixed import statements SHALL resolve without raising `ModuleNotFoundError`, successfully importing `__version__` from `__init__.py`, `StreamingResponseHandler` from `streaming.py`, and `cli` from `sales_agent_cli.py`.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - CLI Functionality Unchanged

_For any_ CLI invocation (commands, arguments, interactions), the fixed code SHALL produce exactly the same behavior as the original code when imports resolve successfully, preserving all command outputs, error handling, AWS interactions, and streaming behavior.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `agentcore-runtime/cli/sales_agent_cli.py`

**Lines**: 16-17

**Specific Changes**:
1. **Change `from cli import __version__`** to `from . import __version__` — uses relative import to get `__version__` from the package's `__init__.py`
2. **Change `from cli.streaming import StreamingResponseHandler`** to `from .streaming import StreamingResponseHandler` — uses relative import to get `StreamingResponseHandler` from the sibling `streaming.py` module

**File**: `agentcore-runtime/cli/__main__.py`

**Line**: 2

**Specific Changes**:
3. **Change `from cli.sales_agent_cli import cli`** to `from .sales_agent_cli import cli` — uses relative import to get the `cli` Click group from the sibling module

No other files require changes. The fix is purely syntactic — import paths change from absolute to relative, with no logic modifications.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm that the absolute imports fail in direct execution contexts.

**Test Plan**: Write tests that attempt to import the modules in a subprocess without the parent directory on `sys.path`, simulating direct script execution. Run these tests on the UNFIXED code to observe `ModuleNotFoundError`.

**Test Cases**:
1. **Direct Import Test**: Import `sales_agent_cli` in a subprocess where `agentcore-runtime` is not on `sys.path` (will fail on unfixed code with `ModuleNotFoundError`)
2. **Main Module Test**: Import `__main__` in a subprocess where `agentcore-runtime` is not on `sys.path` (will fail on unfixed code with `ModuleNotFoundError`)

**Expected Counterexamples**:
- `ModuleNotFoundError: No module named 'cli'` when importing `sales_agent_cli.py` directly
- `ModuleNotFoundError: No module named 'cli'` when importing `__main__.py` directly

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL execution_context WHERE isBugCondition(execution_context) DO
  result := import_module(execution_context)
  ASSERT result.no_import_error
  ASSERT result.version == __version__
  ASSERT result.StreamingResponseHandler IS accessible
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL cli_invocation WHERE NOT isBugCondition(cli_invocation) DO
  ASSERT original_cli(cli_invocation) = fixed_cli(cli_invocation)
END FOR
```

**Testing Approach**: The existing test suite (`test_sales_agent_cli.py`, `test_streaming.py`, `test_time_parser.py`) already covers CLI functionality comprehensively. Running these tests after the fix serves as preservation checking — if all existing tests pass, behavior is preserved.

**Test Plan**: Run the full existing test suite after applying the fix to verify no regressions.

**Test Cases**:
1. **Version Command Preservation**: Verify `cli version` continues to output the correct version string
2. **CLI Help Preservation**: Verify `cli --help` continues to display correct help text
3. **Stack Validation Preservation**: Verify `_get_cli` continues to require and validate stack names
4. **Streaming Preservation**: Verify `StreamingResponseHandler` continues to work in `invoke` and `chat` commands

### Unit Tests

- Test that `from . import __version__` resolves correctly and returns the expected version string
- Test that `from .streaming import StreamingResponseHandler` resolves correctly
- Test that `from .sales_agent_cli import cli` resolves correctly from `__main__.py`
- Run all existing tests in `test_sales_agent_cli.py` to verify no regressions

### Property-Based Tests

- Generate random CLI argument combinations and verify the CLI entry point loads without import errors
- Verify that for any valid command invocation, the output matches expected behavior regardless of execution context

### Integration Tests

- Test `python -m cli version` continues to work from `agentcore-runtime/`
- Test that the full CLI loads and responds to `--help` after the import fix
- Test that `invoke` and `chat` commands can reach the point of AWS interaction (import chain fully resolved)
