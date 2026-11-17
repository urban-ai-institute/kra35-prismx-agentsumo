"""
Tests for replies cut off at max_tokens, with a mocked Anthropic client
(no API calls):
1. The output budget leaves room for a visible reply after thinking
2. A truncated tool_use is neither run nor stored, and the user is told
3. The conversation keeps working on the next turn
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from anthropic.types import Message, TextBlock, ThinkingBlock, ToolUseBlock, Usage

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo import AgentSUMO


def _message(stop_reason, *blocks):
    return Message(
        id="msg_test", type="message", role="assistant", model="claude-sonnet-4-5-20250929",
        stop_reason=stop_reason, stop_sequence=None,
        usage=Usage(input_tokens=1, output_tokens=1), content=list(blocks),
    )


def _block_type(block):
    return block["type"] if isinstance(block, dict) else block.type


def _check_history(messages):
    """The API's checks that a dangling tool_use or an empty block would fail."""
    for i, message in enumerate(messages):
        if isinstance(message["content"], str):
            continue
        assert message["content"], f"message {i} has no content"
        for block in message["content"]:
            if _block_type(block) == "text":
                text = block["text"] if isinstance(block, dict) else block.text
                assert text.strip(), f"message {i} has an empty text block"
        if message["role"] != "assistant":
            continue
        ids = {b["id"] if isinstance(b, dict) else b.id for b in message["content"] if _block_type(b) == "tool_use"}
        following = messages[i + 1]["content"] if i + 1 < len(messages) else []
        answered = {b["tool_use_id"] for b in following if isinstance(b, dict) and b.get("type") == "tool_result"}
        assert ids <= answered, f"tool_use {ids - answered} in message {i} has no tool_result"


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **params):
        _check_history(params["messages"])
        self.calls.append(params)
        return self.responses.pop(0)


class FakeSumo:
    is_connected = True

    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        payload = {"status": "success", "net_file": "/o/networks/gangnam.net.xml"}
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))], isError=False)


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTSUMO_MCP_OUTPUT_BASE", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = AgentSUMO(enable_logging=False)
    agent.mcp_clients["sumo"] = FakeSumo()
    return agent


def _use(agent, *responses):
    fake = FakeMessages(responses)
    agent.claude = SimpleNamespace(messages=fake)
    return fake


def test_output_budget_leaves_room_after_thinking(agent):
    fake = _use(agent, _message("end_turn", TextBlock(type="text", text="ok")))

    asyncio.run(agent.chat("hello"))

    params = fake.calls[0]
    budget = params["thinking"]["budget_tokens"]
    assert budget < params["max_tokens"]
    assert params["max_tokens"] - budget >= 4000
    # Non-streaming requests: the SDK refuses max_tokens above ~21k
    assert params["max_tokens"] <= 21000


def test_truncated_tool_use_is_dropped_and_reported(agent):
    fake = _use(
        agent,
        _message(
            "max_tokens",
            ThinkingBlock(type="thinking", thinking="...", signature="sig"),
            TextBlock(type="text", text="I'll validate the coordinates"),
            ToolUseBlock(type="tool_use", id="toolu_1", name="validate_od_coordinates_tool", input={}),
        ),
        _message("end_turn", TextBlock(type="text", text="ok")),
        _message("end_turn", TextBlock(type="text", text="still ok")),
    )

    reply = asyncio.run(agent.chat("make flows for 9 OD pairs"))

    assert reply.startswith("I'll validate the coordinates")
    assert "cut off" in reply and "not run" in reply
    assert agent.mcp_clients["sumo"].calls == []
    stored = agent.conversation_history[-1]["content"]
    assert "tool_use" not in [_block_type(b) for b in stored]

    # Later turns are accepted (FakeMessages applies the API's history checks)
    assert asyncio.run(agent.chat("turn 2")) == "ok"
    assert asyncio.run(agent.chat("turn 3")) == "still ok"
    assert len(fake.calls) == 3


def test_truncation_inside_tool_loop(agent):
    _use(
        agent,
        _message("tool_use", ToolUseBlock(type="tool_use", id="toolu_1", name="net_convert", input={"osm_file": "x.osm"})),
        # Cut off while starting the next tool call, with no text at all
        _message("max_tokens", TextBlock(type="text", text=""),
                 ToolUseBlock(type="tool_use", id="toolu_2", name="trip_generate", input={})),
        _message("end_turn", TextBlock(type="text", text="ok")),
    )

    reply = asyncio.run(agent.chat("build the network"))

    assert agent.mcp_clients["sumo"].calls == ["net_convert"]
    assert reply.startswith("[Reply cut off")
    assert agent.simulation_state["current_network"] == "/o/networks/gangnam.net.xml"
    assert asyncio.run(agent.chat("continue")) == "ok"
