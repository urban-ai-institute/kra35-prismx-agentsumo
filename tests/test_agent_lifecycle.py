"""
Tests for AgentSUMO MCP client lifecycle, using fake clients (no MCP servers):
1. close() shuts clients in reverse opening order
2. One failing client does not keep the others open
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import sys

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import agentsumo.agent.agent_sumo as agent_module
import agentsumo.client.filesystem_mcp_client as filesystem_module
import agentsumo.client.sqlite_mcp_client as sqlite_module
from agentsumo import AgentSUMO
from agentsumo.core import AgentSUMOConfig


class FakeClient:
    """
    Stand-in for an MCP client. Like the anyio cancel scopes inside the real
    stdio clients, contexts must be exited in reverse order of entry.
    """

    def __init__(self, kind, world, *args, fail_on_exit=False):
        self.kind = kind
        self.world = world
        self.db_path = args[0] if kind == "sqlite" else None
        self.fail_on_exit = fail_on_exit
        self._connected = False

    async def __aenter__(self):
        self.world["stack"].append(self)
        self._connected = True
        self.world["opened"].append(self.kind)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.world["closed"].append(self.kind)
        if self.world["stack"][-1] is not self:
            raise RuntimeError("Attempted to exit a cancel scope that isn't the current task's current cancel scope")
        self.world["stack"].pop()
        self._connected = False
        if self.fail_on_exit:
            raise RuntimeError("shutdown failed")
        return False

    @property
    def is_connected(self):
        return self._connected

    async def list_tools(self):
        names = {
            "sumo": ["net_convert", "sumo_runner"],
            "sqlite": ["read_query", "list_tables"],
            "filesystem": ["read_text_file", "write_file"],
        }[self.kind]
        return [SimpleNamespace(name=n, description="", inputSchema={"type": "object"}) for n in names]


@pytest.fixture
def world(tmp_path, monkeypatch):
    world = {"stack": [], "opened": [], "closed": [], "fail_on_exit": set()}

    def factory(kind):
        def make(*args, **kwargs):
            return FakeClient(kind, world, *args, fail_on_exit=kind in world["fail_on_exit"])
        return make

    monkeypatch.setattr(agent_module, "SUMOMCPClient", factory("sumo"))
    monkeypatch.setattr(sqlite_module, "SQLiteMCPClient", factory("sqlite"))
    monkeypatch.setattr(filesystem_module, "FilesystemMCPClient", factory("filesystem"))

    # Keep every file the agent writes inside tmp_path
    monkeypatch.setenv("AGENTSUMO_MCP_OUTPUT_BASE", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(AgentSUMOConfig, "OUTPUT_DIR", tmp_path / "output")
    return world


def _make_db(path, simulation_id="1_baseline"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE simulations (simulation_id TEXT)")
    conn.execute("INSERT INTO simulations VALUES (?)", (simulation_id,))
    conn.commit()
    conn.close()
    return str(path)


def _agent(tmp_path, **kwargs):
    return AgentSUMO(
        enable_logging=False,
        enable_filesystem_mcp=True,
        filesystem_directories=[str(tmp_path)],
        **kwargs,
    )


def test_close_reverses_opening_order(world, tmp_path):
    db = _make_db(tmp_path / "gangnam_analysis.db")

    async def run():
        agent = _agent(tmp_path)
        await agent.start(db_path=db)
        await agent.close()
        return agent

    agent = asyncio.run(run())

    assert sorted(world["opened"]) == ["filesystem", "sqlite", "sumo"]
    assert world["closed"] == world["opened"][::-1]
    assert world["stack"] == []
    assert all(client is None for client in agent.mcp_clients.values())


def test_close_after_sqlite_enabled_mid_session(world, tmp_path):
    async def run():
        agent = _agent(tmp_path, enable_sqlite_mcp=None)
        await agent.start()  # no DB yet: SUMO + Filesystem only
        # xml_to_sqlite_tool created the first DB during the session
        agent.simulation_state["current_db"] = _make_db(tmp_path / "gangnam_analysis.db")
        await agent._check_and_enable_sqlite_if_needed()
        await agent.close()

    asyncio.run(run())

    assert world["opened"] == ["sumo", "filesystem", "sqlite"]
    assert world["closed"] == ["sqlite", "filesystem", "sumo"]
    assert world["stack"] == []


def test_failing_client_does_not_block_the_others(world, tmp_path):
    db = _make_db(tmp_path / "gangnam_analysis.db")
    world["fail_on_exit"] = {"sqlite", "filesystem"}

    async def run():
        agent = _agent(tmp_path)
        await agent.start(db_path=db)
        await agent.close()

    asyncio.run(run())

    assert sorted(world["closed"]) == ["filesystem", "sqlite", "sumo"]
    assert world["stack"] == []


def test_sqlite_reconnects_when_current_db_changes(world, tmp_path):
    gangnam = _make_db(tmp_path / "gangnam_analysis.db")
    hongdae = _make_db(tmp_path / "hongdae_analysis.db", "1_baseline_hongdae")

    async def run():
        agent = _agent(tmp_path)
        await agent.start(db_path=gangnam)
        # xml_to_sqlite_tool wrote a new DB for another area
        agent.simulation_state["current_db"] = hongdae
        await agent._check_and_enable_sqlite_if_needed()
        connected_to = agent.mcp_clients["sqlite"].db_path
        tool_names = [t["name"] for t in agent.tools]
        # Nothing to do while the DB stays the same
        await agent._check_and_enable_sqlite_if_needed()
        reopened = world["opened"].count("sqlite")
        await agent.close()
        return agent, connected_to, tool_names, reopened

    agent, connected_to, tool_names, reopened = asyncio.run(run())

    assert connected_to == hongdae
    assert agent.simulation_state["sqlite_enabled"] is True
    assert reopened == 2
    assert tool_names.count("read_query") == 1
    assert world["closed"] == ["sqlite", "sqlite", "filesystem", "sumo"]
    assert world["stack"] == []


def test_agent_starts_without_filesystem_mcp(world, tmp_path, monkeypatch):
    db = _make_db(tmp_path / "gangnam_analysis.db")

    class NoNode(FakeClient):
        async def __aenter__(self):
            raise RuntimeError("Filesystem MCP Server connection failed - [Errno 2] No such file or directory: 'npx'")

    monkeypatch.setattr(filesystem_module, "FilesystemMCPClient", lambda *a, **k: NoNode("filesystem", world))

    async def run():
        agent = _agent(tmp_path)
        await agent.start(db_path=db)
        names = [t["name"] for t in agent.tools]
        await agent.close()
        return agent, names

    agent, names = asyncio.run(run())

    assert "net_convert" in names and "read_query" in names
    assert "read_text_file" not in names
    assert world["closed"] == ["sqlite", "sumo"]
