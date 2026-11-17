"""
Tests for output base directory resolution:
1. A relative AGENTSUMO_MCP_OUTPUT_BASE is made absolute
2. An unwritable working directory falls back to ~/agentsumo-output
"""

import os
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.utils import path_utils


def test_relative_env_base_is_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTSUMO_MCP_OUTPUT_BASE", "runs")

    out = path_utils.get_output_path("output/networks")

    assert out == tmp_path / "runs" / "output" / "networks"
    assert out.is_absolute() and out.is_dir()


def test_unwritable_cwd_falls_back_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTSUMO_MCP_OUTPUT_BASE", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(path_utils, "_FALLBACK_BASE_DIR", tmp_path / "fallback")
    real_access = os.access
    monkeypatch.setattr(path_utils.os, "access", lambda p, mode: False if Path(p) == tmp_path else real_access(p, mode))

    assert path_utils.get_output_path("output") == tmp_path / "fallback" / "output"
