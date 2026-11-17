"""
Tests for the SQLite MCP Server launch:
1. The server starts from the installed mcp-server-sqlite package
   (no local sqlite-mcp-server/ folder needed)
2. It exposes the six underscore-named tools the agent's prompts use
3. read_query returns rows from the database
"""

import asyncio
import sqlite3
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo.client.sqlite_mcp_client import SQLiteMCPClient


EXPECTED_TOOLS = {
    "read_query",
    "write_query",
    "create_table",
    "list_tables",
    "describe_table",
    "append_insight",
}


def test_sqlite_mcp_server_launches_from_installed_package(tmp_path):
    db_path = tmp_path / "simulations.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE edges (id TEXT, speed REAL)")
    conn.execute("INSERT INTO edges VALUES ('edge_1', 13.9)")
    conn.commit()
    conn.close()

    async def run():
        async with SQLiteMCPClient(str(db_path), connection_timeout=30.0) as client:
            tools = {tool.name for tool in await client.list_tools()}
            result = await client.call_tool("read_query", {"query": "SELECT id FROM edges"})
            return tools, result

    tools, result = asyncio.run(run())

    assert tools == EXPECTED_TOOLS
    assert "edge_1" in result.content[0].text
