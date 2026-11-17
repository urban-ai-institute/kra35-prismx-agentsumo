"""
Tests for AgentSUMO simulation state tracking (no API, MCP or SUMO needed):
1. Failed tool results leave the state untouched
2. A state file poisoned by older versions is cleaned on restore
3. Tools that write a new route file update current_routes
"""

import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo import AgentSUMO
from agentsumo.agent.prompts import PromptBuilder


def _result(payload, is_error=False):
    """Mimic an MCP CallToolResult with one text block."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(content=[SimpleNamespace(text=text)], isError=is_error)


@pytest.fixture
def agent(tmp_path, monkeypatch):
    # State file goes to <tmp>/output/.agentsumo_state.json
    monkeypatch.setenv("AGENTSUMO_MCP_OUTPUT_BASE", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return AgentSUMO(enable_logging=False)


def _good_state(agent, tmp_path):
    db = tmp_path / "gangnam_analysis.db"
    db.write_bytes(b"x")
    agent.simulation_state.update({
        "current_network": "/o/networks/gangnam.net.xml",
        "baseline_network": "/o/networks/gangnam.net.xml",
        "current_routes": "/o/trips/gangnam.rou.xml",
        "last_results": ["/o/simulations/tripinfo.xml"],
        "current_db": str(db),
        "sqlite_enabled": True,
        "simulations": [{"simulation_id": "1_baseline", "trip_count": 5, "db_file": str(db)}],
    })
    return json.loads(json.dumps(agent.simulation_state))


@pytest.mark.parametrize("tool, payload", [
    ("xml_to_sqlite_tool", {"status": "error", "message": "no such file"}),
    ("route_generate", {"status": "error", "message": "duarouter failed"}),
    ("sumo_runner", {"status": "error", "output_files": [], "message": "x"}),
    ("sumo_runner", {"status": "validation_error", "output_files": [], "message": "x"}),
    ("net_convert", {"status": "error", "message": "netconvert failed"}),
    ("flow_generation_tool", {"status": "error", "message": "No shortest path found."}),
    ("edge_edit_tool", {"status": "error", "message": "Road not found."}),
])
def test_failed_tool_leaves_state_unchanged(agent, tmp_path, tool, payload):
    before = _good_state(agent, tmp_path)

    agent._update_state(tool, _result(payload))

    assert agent.simulation_state == before
    # The context still renders
    agent.prompt_builder.format_context(agent.simulation_state)


def test_mcp_error_result_leaves_state_unchanged(agent, tmp_path):
    before = _good_state(agent, tmp_path)

    agent._update_state("route_generate", _result("Error executing tool route_generate: boom", is_error=True))

    assert agent.simulation_state == before


def test_poisoned_state_file_recovers_on_restore(agent, tmp_path, monkeypatch):
    db = tmp_path / "x_analysis.db"
    db.write_bytes(b"x")
    state_file = agent._get_state_file_path()
    state_file.write_text(json.dumps({
        "current_db": str(db),
        "sqlite_enabled": True,
        "simulations": [
            {"simulation_id": None, "trip_count": 0},
            {"trip_count": 3},
            "garbage",
            {"simulation_id": "1_baseline", "trip_count": 5, "db_file": str(db)},
        ],
    }))

    fresh = AgentSUMO(enable_logging=False)
    fresh._restore_state()

    assert [s["simulation_id"] for s in fresh.simulation_state["simulations"]] == ["1_baseline"]
    context = fresh.prompt_builder.format_context(fresh.simulation_state)
    assert "<simulations>1_baseline</simulations>" in context


def test_format_context_skips_malformed_simulations():
    builder = PromptBuilder()
    state = {
        "current_db": "/o/analysis/a.db",
        "sqlite_enabled": True,
        "simulations": [{"simulation_id": None}, {}, None, {"simulation_id": "2_policy", "db_file": "/o/analysis/a.db"}],
    }

    context = builder.format_context(state)

    assert "<simulations>2_policy</simulations>" in context


@pytest.mark.parametrize("tool", ["route_generate", "flow_generation_tool",
                                  "vehicle_generation_tool", "vehicle_type_edit_tool"])
def test_route_writing_tools_update_current_routes(agent, tmp_path, tool):
    _good_state(agent, tmp_path)

    agent._update_state(tool, _result({"status": "success", "route_file": "/o/trips/new.rou.xml"}))

    assert agent.simulation_state["current_routes"] == "/o/trips/new.rou.xml"


def test_edge_edit_clears_current_routes(agent, tmp_path):
    _good_state(agent, tmp_path)

    agent._update_state("edge_edit_tool", _result({
        "status": "success", "net_file": "/o/networks/gangnam_edgeedit.net.xml", "route_file": None,
    }))

    assert agent.simulation_state["current_network"] == "/o/networks/gangnam_edgeedit.net.xml"
    assert agent.simulation_state["current_routes"] is None


def test_lane_reduction_keeps_current_routes(agent, tmp_path):
    before = _good_state(agent, tmp_path)

    agent._update_state("reduce_lanes_tool", _result({
        "status": "success", "net_file": "/o/networks/gangnam_lanes.net.xml",
        "route_file": before["current_routes"],
    }))

    assert agent.simulation_state["current_routes"] == before["current_routes"]
