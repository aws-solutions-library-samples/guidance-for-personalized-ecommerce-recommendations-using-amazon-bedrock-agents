"""
Bug condition exploration tests for SYSTEM_PROMPT restoration.

These tests encode the EXPECTED behavior: SYSTEM_PROMPT should match the original
AGENT_INSTRUCTION from sales_agent/sales_agent_stack.py verbatim.

On UNFIXED code, all tests are expected to FAIL — confirming the bug exists.
After the fix, all tests should PASS.

Validates: Requirements 1.1, 1.2, 2.1, 2.2
"""

import ast
import re
import os


def _extract_string_constant(filepath: str, variable_name: str) -> str:
    """Extract a module-level string constant from a Python file using AST parsing.

    This avoids importing the module (which would trigger side effects like
    Config.load() and AWS SDK calls).
    """
    with open(filepath, "r") as f:
        tree = ast.parse(f.read(), filename=filepath)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == variable_name:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    raise ValueError(f"Could not find string constant '{variable_name}' in {filepath}")


# Paths relative to the agent-core directory (tests run from agent-core/)
_AGENT_PY = os.path.join(os.path.dirname(__file__), "..", "agent.py")

# Extract SYSTEM_PROMPT without importing the module
SYSTEM_PROMPT = _extract_string_constant(_AGENT_PY, "SYSTEM_PROMPT")

# The original AGENT_INSTRUCTION from sales_agent/sales_agent_stack.py (verbatim)
EXPECTED_PROMPT = '''You are a professional sales expert which can help customer on:
1. Allows searching for products based on a specified condition, which defines customer requirements for the product.
2. Compares products based on user input, which includes user ID, product search condition, and user preferences.
3. Generates personalized product recommendations for a user based on their ID and preferences.
4. Reference sales pitch knowledge base provide sample sales toolkit
5. Respond to the customer in the same language they use to ask you questions.
'''


def test_system_prompt_matches_original_agent_instruction():
    """
    **Validates: Requirements 2.1, 2.2**

    Assert SYSTEM_PROMPT is identical to the original AGENT_INSTRUCTION.
    Full string comparison — any deviation means the bug is present.
    """
    assert SYSTEM_PROMPT == EXPECTED_PROMPT, (
        f"SYSTEM_PROMPT does not match original AGENT_INSTRUCTION.\n"
        f"--- EXPECTED ---\n{EXPECTED_PROMPT}\n"
        f"--- ACTUAL ---\n{SYSTEM_PROMPT}"
    )


def test_system_prompt_contains_five_numbered_points():
    """
    **Validates: Requirements 1.1, 2.1**

    Assert SYSTEM_PROMPT contains exactly 5 numbered instruction points.
    The original prompt has points 1-5; the simplified version only has 4.
    """
    numbered_lines = re.findall(r"^\d+\.", SYSTEM_PROMPT, re.MULTILINE)
    assert len(numbered_lines) == 5, (
        f"Expected 5 numbered instruction points, found {len(numbered_lines)}. "
        f"Matched lines: {numbered_lines}"
    )


def test_system_prompt_contains_knowledge_base_reference():
    """
    **Validates: Requirements 1.2, 2.2**

    Assert SYSTEM_PROMPT contains the knowledge base reference instruction
    (original point 4), which is entirely missing from the simplified prompt.
    """
    expected_phrase = "Reference sales pitch knowledge base provide sample sales toolkit"
    assert expected_phrase in SYSTEM_PROMPT, (
        f"SYSTEM_PROMPT is missing the knowledge base reference instruction: "
        f"'{expected_phrase}'"
    )


def test_system_prompt_contains_full_language_instruction():
    """
    **Validates: Requirements 1.1, 2.1**

    Assert SYSTEM_PROMPT contains "to ask you questions" in the language-matching
    instruction. The simplified prompt truncates this to just "they use."
    """
    expected_phrase = "to ask you questions"
    assert expected_phrase in SYSTEM_PROMPT, (
        f"SYSTEM_PROMPT is missing the full language instruction ending: "
        f"'{expected_phrase}'. The current prompt likely truncates point 5."
    )
