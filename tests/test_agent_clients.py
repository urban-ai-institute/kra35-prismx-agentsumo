"""
Tests for the MCP client classes used by the agent (no network needed):
1. A failed Filesystem MCP connection unwinds what it opened, so clients
   opened before it still shut down cleanly
"""

import asyncio
import logging
from pathlib import Path
import sqlite3
import sys

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo.client.filesystem_mcp_client import FilesystemMCPClient
from agentsumo.client.sqlite_mcp_client import SQLiteMCPClient


def test_filesystem_client_allows_time_for_first_npx_download():
    assert FilesystemMCPClient("/tmp").connection_timeout >= 60


@pytest.mark.skipif(sys.platform == "win32", reason="fake npx is a POSIX script")
def test_failed_filesystem_connect_leaves_no_open_scopes(tmp_path, monkeypatch, caplog):
    # An "npx" that dies at once, like an offline first run
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_npx = bin_dir / "npx"
    fake_npx.write_text(f"#!{sys.executable}\nimport sys\nsys.stderr.write('npm ERR! network\\n')\nsys.exit(1)\n")
    fake_npx.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + "/usr/bin:/bin")

    db_path = tmp_path / "simulations.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (x)")
    conn.close()

    async def run():
        sqlite_client = SQLiteMCPClient(str(db_path), connection_timeout=30.0)
        await sqlite_client.__aenter__()
        fs_client = FilesystemMCPClient([str(tmp_path)], connection_timeout=20.0)
        with pytest.raises(RuntimeError):
            await fs_client.__aenter__()
        leftovers = (fs_client._stdio_context_manager, fs_client._session_context_manager)
        await sqlite_client.__aexit__(None, None, None)
        return leftovers, sqlite_client.is_connected

    with caplog.at_level(logging.WARNING):
        leftovers, still_connected = asyncio.run(run())

    assert leftovers == (None, None)
    assert not still_connected
    # Before the fix, closing the SQLite client hit the half-open
    # Filesystem cancel scopes ("Error while closing connection ...")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], \
        [r.getMessage() for r in caplog.records]
