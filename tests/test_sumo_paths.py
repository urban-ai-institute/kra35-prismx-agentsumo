"""
Tests for SUMO tool/data path resolution across install layouts:
1. Linux / Windows / Homebrew: SUMO_HOME/tools, SUMO_HOME/data
2. macOS framework installer: SUMO_HOME/share/sumo/tools, .../data
"""

from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.settings.settings import SUMOEnvironment


def _env_with_home(monkeypatch, sumo_home):
    monkeypatch.setattr(SUMOEnvironment, "SUMO_HOME", str(sumo_home))
    return SUMOEnvironment


def test_flat_layout(tmp_path, monkeypatch):
    (tmp_path / "tools").mkdir()
    (tmp_path / "data").mkdir()
    env = _env_with_home(monkeypatch, tmp_path)

    assert env.get_tool_path("randomTrips.py") == str(tmp_path / "tools" / "randomTrips.py")
    assert env.get_data_path("typemap/osmNetconvert.typ.xml") == str(tmp_path / "data" / "typemap/osmNetconvert.typ.xml")


def test_macos_framework_layout(tmp_path, monkeypatch):
    share = tmp_path / "share" / "sumo"
    (share / "tools").mkdir(parents=True)
    (share / "data").mkdir()
    env = _env_with_home(monkeypatch, tmp_path)

    assert env.get_tool_path("randomTrips.py") == str(share / "tools" / "randomTrips.py")
    assert env.get_data_path("typemap/osmNetconvert.typ.xml") == str(share / "data" / "typemap/osmNetconvert.typ.xml")
