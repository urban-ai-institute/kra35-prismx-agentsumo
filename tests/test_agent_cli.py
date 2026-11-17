"""
Tests for the CLI entry point (chat.py), without starting the agent:
1. .env values are read like python-dotenv does (quotes, inline comments)
   and never override variables already set in the shell
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).parent.parent


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
