"""
Tests for the CLI entry point (chat.py), without starting the agent:
1. .env values are read like python-dotenv does (quotes, inline comments)
   and never override variables already set in the shell
2. The CLI enables the Filesystem MCP on the guides and output directories
"""

import asyncio
import builtins
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).parent.parent

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))


def test_env_file_parsing_and_shell_precedence(tmp_path):
    # chat.py reads the .env next to itself, so run a copy from tmp_path
    shutil.copy(PROJECT_ROOT / "chat.py", tmp_path / "chat.py")
    (tmp_path / ".env").write_text(
        'ANTHROPIC_API_KEY="sk-ant-api03-quoted"\n'
        "MAPBOX_TOKEN=pk.test  # inline comment\n"
        "SUMO_HOME=\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "MAPBOX_TOKEN")}
    env["SUMO_HOME"] = "/shell/sumo"
    env["PYTHONPATH"] = os.pathsep.join([str(PROJECT_ROOT), env.get("PYTHONPATH", "")])

    # Import chat.py (module level only, main() does not run)
    code = (
        "import json, os, runpy, sys; "
        "runpy.run_path(sys.argv[1], run_name='chat'); "
        "print(json.dumps({k: os.environ.get(k) for k in ('ANTHROPIC_API_KEY', 'MAPBOX_TOKEN', 'SUMO_HOME')}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "chat.py")],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True,
    ).stdout

    values = json.loads(out.strip().splitlines()[-1])
    assert values == {
        "ANTHROPIC_API_KEY": "sk-ant-api03-quoted",
        "MAPBOX_TOKEN": "pk.test",
        "SUMO_HOME": "/shell/sumo",
    }


def test_cli_enables_filesystem_mcp(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTSUMO_MCP_OUTPUT_BASE", str(tmp_path))
    spec = importlib.util.spec_from_file_location("agentsumo_chat_cli", PROJECT_ROOT / "chat.py")
    chat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chat)

    created = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            created.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    def end_of_input(prompt=""):
        raise EOFError

    monkeypatch.setattr(chat, "AgentSUMO", FakeAgent)
    monkeypatch.setattr(builtins, "input", end_of_input)
    asyncio.run(chat.main())

    assert created["enable_filesystem_mcp"] is True
    guides, output = (Path(d) for d in created["filesystem_directories"])
    assert (guides / "rerouter.md").is_file()
    assert (guides / "vss.md").is_file() and (guides / "vtype.md").is_file()
    assert output == tmp_path / "output"
    assert output.is_dir()  # the Filesystem MCP Server rejects missing directories
