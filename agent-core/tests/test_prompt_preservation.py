"""
Preservation property tests for agent-core bugfix.

These tests verify that all NON-PROMPT behavior is unchanged by the bugfix.
They are written BEFORE the fix and must PASS on unfixed code, confirming
the baseline behavior we need to preserve.

Validates: Requirements 3.1, 3.2, 3.3
"""

import ast
import json
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Helpers: AST-based extraction to avoid importing agent.py (which triggers
# Config.load() and AWS SDK calls at module level).
# ---------------------------------------------------------------------------

_AGENT_PY = os.path.join(os.path.dirname(__file__), "..", "agent.py")


def _parse_agent_module():
    """Return the AST tree of agent.py."""
    with open(_AGENT_PY, "r") as f:
        return ast.parse(f.read(), filename=_AGENT_PY)


def _extract_function_source(func_name: str) -> str:
    """Extract the source text of a top-level function from agent.py."""
    with open(_AGENT_PY, "r") as f:
        source = f.read()
    tree = ast.parse(source, filename=_AGENT_PY)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return ast.get_source_segment(source, node)
    raise ValueError(f"Function '{func_name}' not found in agent.py")


# ---------------------------------------------------------------------------
# Stub modules that would trigger AWS SDK calls on import
# ---------------------------------------------------------------------------

def _build_stub_modules():
    """Create stub modules so we can import agent.py without AWS calls."""
    # Stub bedrock_agentcore.runtime
    runtime_mod = types.ModuleType("bedrock_agentcore.runtime")
    agentcore_mod = types.ModuleType("bedrock_agentcore")

    class FakeApp:
        def entrypoint(self, fn):
            fn._is_entrypoint = True
            return fn

        def websocket(self, fn):
            fn._is_websocket = True
            return fn

        def run(self):
            pass

    runtime_mod.BedrockAgentCoreApp = FakeApp
    agentcore_mod.runtime = runtime_mod

    # Stub bedrock_agentcore.memory
    memory_mod = types.ModuleType("bedrock_agentcore.memory")
    memory_mod.MemorySessionManager = MagicMock
    constants_mod = types.ModuleType("bedrock_agentcore.memory.constants")
    constants_mod.ConversationalMessage = MagicMock
    constants_mod.MessageRole = MagicMock
    memory_mod.constants = constants_mod

    # Stub strands
    strands_mod = types.ModuleType("strands")
    strands_mod.Agent = MagicMock

    # Stub config
    config_mod = types.ModuleType("config")

    class FakeConfig:
        model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
        aoss_collection_id = "fake"
        aoss_region = "us-east-1"
        item_table_name = "item_table"
        user_table_name = "user_table"
        recommender_arn = None
        parameter_store_prefix = "/agentcore/sales-agent/"

        @classmethod
        def load(cls):
            return cls()

    config_mod.Config = FakeConfig

    # Stub memory module
    mem_mod = types.ModuleType("memory")
    mem_mod.MemoryClient = MagicMock

    # Stub tools
    tools_mod = types.ModuleType("tools")

    def _fake_search_product():
        pass

    def _fake_compare_product():
        pass

    def _fake_get_recommendation():
        pass

    _fake_search_product.__name__ = "search_product"
    _fake_compare_product.__name__ = "compare_product"
    _fake_get_recommendation.__name__ = "get_recommendation"

    tools_mod.search_product = _fake_search_product
    tools_mod.compare_product = _fake_compare_product
    tools_mod.get_recommendation = _fake_get_recommendation

    # Sub-modules for tools
    sp_mod = types.ModuleType("tools.search_product")
    sp_mod.search_product = _fake_search_product
    cp_mod = types.ModuleType("tools.compare_product")
    cp_mod.compare_product = _fake_compare_product
    gr_mod = types.ModuleType("tools.get_recommendation")
    gr_mod.get_recommendation = _fake_get_recommendation

    return {
        "bedrock_agentcore": agentcore_mod,
        "bedrock_agentcore.runtime": runtime_mod,
        "bedrock_agentcore.memory": memory_mod,
        "bedrock_agentcore.memory.constants": constants_mod,
        "strands": strands_mod,
        "config": config_mod,
        "memory": mem_mod,
        "tools": tools_mod,
        "tools.search_product": sp_mod,
        "tools.compare_product": cp_mod,
        "tools.get_recommendation": gr_mod,
    }


# ---------------------------------------------------------------------------
# Fixture: import agent module with stubs
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent_module():
    """Import agent.py with all AWS-dependent modules stubbed out."""
    stubs = _build_stub_modules()
    saved = {}
    # Add agent-core to sys.path so `import agent` resolves
    agent_core_dir = os.path.join(os.path.dirname(__file__), "..")
    abs_agent_core = os.path.abspath(agent_core_dir)

    for name, mod in stubs.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    if abs_agent_core not in sys.path:
        sys.path.insert(0, abs_agent_core)

    # Remove cached agent module so it re-imports with our stubs
    if "agent" in sys.modules:
        del sys.modules["agent"]

    import agent  # noqa: E402

    yield agent

    # Cleanup
    for name, original in saved.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original
    if "agent" in sys.modules:
        del sys.modules["agent"]
    if abs_agent_core in sys.path:
        sys.path.remove(abs_agent_core)


# ===========================================================================
# Property 2a - Tool List Preservation
# ===========================================================================

def test_tool_list_preservation(agent_module):
    """
    **Validates: Requirements 3.1**

    Assert create_agent() passes the correct tools list:
    [search_product, compare_product, get_recommendation].
    """
    with patch.object(agent_module, "Agent") as mock_agent_cls:
        mock_agent_cls.return_value = MagicMock()
        agent_module.create_agent()

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args
        tools_arg = call_kwargs.kwargs.get("tools") or call_kwargs[1].get("tools")

        tool_names = [t.__name__ for t in tools_arg]
        assert tool_names == ["search_product", "compare_product", "get_recommendation"], (
            f"Expected tools [search_product, compare_product, get_recommendation], "
            f"got {tool_names}"
        )


# ===========================================================================
# Property 2b - Model ID Preservation
# ===========================================================================

def test_model_id_preservation(agent_module):
    """
    **Validates: Requirements 3.1**

    Assert create_agent() uses config.model_id as the model parameter.
    """
    with patch.object(agent_module, "Agent") as mock_agent_cls:
        mock_agent_cls.return_value = MagicMock()
        agent_module.create_agent()

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args
        model_arg = call_kwargs.kwargs.get("model") or call_kwargs[1].get("model")

        assert model_arg == agent_module.config.model_id, (
            f"Expected model '{agent_module.config.model_id}', got '{model_arg}'"
        )


# ===========================================================================
# Property 2c - Response Format Preservation (HTTP)
# ===========================================================================

@given(prompt=st.text(min_size=1, max_size=200))
@settings(max_examples=20)
def test_http_response_format_preservation(prompt):
    """
    **Validates: Requirements 3.3**

    For any prompt string, the HTTP invoke entrypoint yields JSON containing
    exactly a "result" or "error" key.
    """
    stubs = _build_stub_modules()
    saved = {}
    agent_core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    for name, mod in stubs.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    if agent_core_dir not in sys.path:
        sys.path.insert(0, agent_core_dir)
    if "agent" in sys.modules:
        del sys.modules["agent"]

    try:
        import agent as ag

        # Mock the Agent to return a canned response
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "test response"

        with patch.object(ag, "Agent", return_value=mock_agent_instance):
            # Also ensure memory_client is None so we skip memory calls
            original_mc = ag.memory_client
            ag.memory_client = None
            try:
                import asyncio

                async def run_invoke():
                    payload = {"prompt": prompt, "session_id": "test-session"}
                    gen = await ag.invoke(payload)
                    results = []
                    async for chunk in gen:
                        results.append(chunk)
                    return results

                chunks = asyncio.get_event_loop().run_until_complete(run_invoke())

                for chunk in chunks:
                    parsed = json.loads(chunk)
                    keys = set(parsed.keys())
                    assert keys == {"result"} or keys == {"error"}, (
                        f"HTTP response must have exactly 'result' or 'error' key, "
                        f"got keys: {keys}"
                    )
            finally:
                ag.memory_client = original_mc
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if "agent" in sys.modules:
            del sys.modules["agent"]
        if agent_core_dir in sys.path:
            sys.path.remove(agent_core_dir)


# ===========================================================================
# Property 2d - Response Format Preservation (WebSocket)
# ===========================================================================

@given(prompt=st.text(min_size=1, max_size=200))
@settings(max_examples=20)
def test_ws_response_format_preservation(prompt):
    """
    **Validates: Requirements 3.3**

    For any prompt payload, the WebSocket handler sends JSON containing
    exactly a "result" or "error" key.
    """
    stubs = _build_stub_modules()
    saved = {}
    agent_core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    for name, mod in stubs.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    if agent_core_dir not in sys.path:
        sys.path.insert(0, agent_core_dir)
    if "agent" in sys.modules:
        del sys.modules["agent"]

    try:
        import agent as ag

        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "test ws response"

        with patch.object(ag, "Agent", return_value=mock_agent_instance):
            original_mc = ag.memory_client
            ag.memory_client = None
            try:
                import asyncio

                mock_ws = AsyncMock()
                payload_json = json.dumps({"prompt": prompt, "session_id": "ws-session"})

                # Make receive_text return our payload once, then raise to exit loop
                mock_ws.receive_text = AsyncMock(
                    side_effect=[payload_json, Exception("close")]
                )
                sent_messages = []

                async def capture_send(text):
                    sent_messages.append(text)

                mock_ws.send_text = AsyncMock(side_effect=capture_send)
                mock_ws.accept = AsyncMock()

                async def run_ws():
                    await ag.ws_handler(mock_ws, {})

                asyncio.get_event_loop().run_until_complete(run_ws())

                assert len(sent_messages) >= 1, "WebSocket handler should send at least one message"
                for msg in sent_messages:
                    parsed = json.loads(msg)
                    keys = set(parsed.keys())
                    assert keys == {"result"} or keys == {"error"}, (
                        f"WS response must have exactly 'result' or 'error' key, "
                        f"got keys: {keys}"
                    )
            finally:
                ag.memory_client = original_mc
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if "agent" in sys.modules:
            del sys.modules["agent"]
        if agent_core_dir in sys.path:
            sys.path.remove(agent_core_dir)


# ===========================================================================
# Property 2e - Memory Flow Preservation
# ===========================================================================

def test_memory_flow_preservation(agent_module):
    """
    **Validates: Requirements 3.2**

    When invoked with a session_id and memory_client is active, assert:
    - get_history is called with the session_id
    - store_turn is called for both user and assistant roles
    """
    mock_memory = MagicMock()
    mock_memory.get_history.return_value = []

    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = "memory test response"

    with patch.object(agent_module, "Agent", return_value=mock_agent_instance), \
         patch.object(agent_module, "memory_client", mock_memory):

        import asyncio

        async def run_invoke():
            payload = {"prompt": "test prompt", "session_id": "mem-session-123"}
            gen = await agent_module.invoke(payload)
            results = []
            async for chunk in gen:
                results.append(chunk)
            return results

        asyncio.get_event_loop().run_until_complete(run_invoke())

        # Verify get_history called with session_id
        mock_memory.get_history.assert_called_once_with("mem-session-123")

        # Verify store_turn called for user and assistant
        store_calls = mock_memory.store_turn.call_args_list
        assert len(store_calls) == 2, (
            f"Expected 2 store_turn calls (user + assistant), got {len(store_calls)}"
        )

        # User turn
        user_call = store_calls[0]
        assert user_call.args[0] == "mem-session-123"  # session_id
        assert user_call.args[1] == "user"  # actor_id
        assert user_call.args[2] == "user"  # role
        assert user_call.args[3] == "test prompt"  # content

        # Assistant turn
        asst_call = store_calls[1]
        assert asst_call.args[0] == "mem-session-123"  # session_id
        assert asst_call.args[1] == "assistant"  # actor_id
        assert asst_call.args[2] == "assistant"  # role
        assert asst_call.args[3] == "memory test response"  # content


# ===========================================================================
# Property 2f - History Context Format Preservation
# ===========================================================================

def test_build_history_context_empty(agent_module):
    """
    **Validates: Requirements 3.2**

    _build_history_context with empty list returns empty string.
    """
    result = agent_module._build_history_context([])
    assert result == "", f"Expected empty string for empty history, got: '{result}'"


@given(
    history=st.lists(
        st.fixed_dictionaries({
            "role": st.sampled_from(["user", "assistant", "system"]),
            "content": st.text(min_size=1, max_size=100),
        }),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=30)
def test_build_history_context_format_preservation(history):
    """
    **Validates: Requirements 3.2**

    For any non-empty list of {"role": str, "content": str} dicts,
    _build_history_context() output:
    - starts with "Previous conversation:"
    - contains all role/content pairs from the input
    """
    stubs = _build_stub_modules()
    saved = {}
    agent_core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    for name, mod in stubs.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    if agent_core_dir not in sys.path:
        sys.path.insert(0, agent_core_dir)
    if "agent" in sys.modules:
        del sys.modules["agent"]

    try:
        import agent as ag

        result = ag._build_history_context(history)

        # Must start with the header
        assert result.startswith("Previous conversation:"), (
            f"History context must start with 'Previous conversation:', got: '{result[:50]}'"
        )

        # Must contain all role/content pairs
        for turn in history:
            role = turn["role"]
            content = turn["content"]
            expected_line = f"  {role}: {content}"
            assert expected_line in result, (
                f"Missing turn in history context: '{expected_line}'"
            )
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if "agent" in sys.modules:
            del sys.modules["agent"]
        if agent_core_dir in sys.path:
            sys.path.remove(agent_core_dir)
