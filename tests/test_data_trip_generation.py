"""
Tests for trip/route/net generation error handling:
1. Failed SUMO tools report their stderr, not only "non-zero exit status 1"
Fake tools stand in for SUMO; tests that need real SUMO binaries are skipped
when SUMO_HOME/bin/sumo is missing.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.baseline.net_converter import NetConverter
from agentsumo_mcp.baseline.route_generator import RouteGenerator
from agentsumo_mcp.baseline.trip_generator import TripGenerator, _tool_error
from agentsumo_mcp.settings.settings import SUMOEnvironment

from test_data_xml_to_sqlite import NET_XML

HAS_SUMO = os.path.exists(SUMOEnvironment.get_binary_path("sumo"))
needs_sumo = pytest.mark.skipif(not HAS_SUMO, reason="SUMO_HOME/bin/sumo not found")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="fake tool is a shebang script")

FAIL_STDERR = "Warning: something harmless\nError: the real reason it failed.\nQuitting (on error).\n"


def _fake_binary(tmp_path, name, stderr=FAIL_STDERR, code=1):
    """An executable that prints to stderr and exits with `code` (stands in for a SUMO binary)."""
    path = tmp_path / name
    path.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stderr.write({stderr!r})\nsys.exit({code})\n"
    )
    path.chmod(0o755)
    return str(path)


class FakeEnv:
    """Delegates to the real SUMO environment, overriding chosen binaries/tools."""

    def __init__(self, binaries=None, tools=None):
        self.binaries, self.tools = binaries or {}, tools or {}

    def get_binary_path(self, name):
        return self.binaries.get(name) or SUMOEnvironment.get_binary_path(name)

    def get_tool_path(self, name):
        return self.tools.get(name) or SUMOEnvironment.get_tool_path(name)

    def get_data_path(self, name):
        return SUMOEnvironment.get_data_path(name)


# ------------------------------------------------------------
# 1. Tool stderr reaches the error message
# ------------------------------------------------------------

def test_tool_error_keeps_a_bounded_tail():
    long_err = "".join(f"Warning: line {i}\n" for i in range(2000)) + "Error: final reason\n"
    msg = _tool_error("netconvert", subprocess.CompletedProcess([], 1, stdout="", stderr=long_err))
    assert msg.startswith("netconvert failed (exit code 1): ...")
    assert msg.endswith("Error: final reason")
    assert len(msg) < 2100


@posix_only
def test_netconvert_error_includes_stderr(tmp_path):
    nc = NetConverter()
    nc.environment = FakeEnv(binaries={"netconvert": _fake_binary(tmp_path, "netconvert")})
    osm = tmp_path / "a.osm"
    osm.write_text("<osm/>")

    result = nc.convert(str(osm), city_en="x", output_dir=str(tmp_path / "out"))
    assert result["status"] == "error"
    assert "netconvert failed (exit code 1)" in result["message"]
    assert "Error: the real reason it failed." in result["message"]


@posix_only
def test_duarouter_error_includes_stderr(tmp_path):
    rg = RouteGenerator()
    rg.environment = FakeEnv(binaries={"duarouter": _fake_binary(tmp_path, "duarouter")})

    result = rg.generate(str(tmp_path / "n.net.xml"), str(tmp_path / "t.trips.xml"),
                         output_dir=str(tmp_path / "out"))
    assert result["status"] == "error"
    assert "duarouter failed (exit code 1)" in result["message"]
    assert "Error: the real reason it failed." in result["message"]


@posix_only
def test_zone_od_polyconvert_error_includes_stderr(tmp_path):
    tg = TripGenerator()
    tg.environment = FakeEnv(binaries={"polyconvert": _fake_binary(tmp_path, "polyconvert")})
    net = tmp_path / "x.net.xml"
    net.write_text(NET_XML)

    result = tg.generate("RealOD", str(net), od_type="zone", od_data_file=str(tmp_path / "od.csv"),
                         zone_shp_file=str(tmp_path / "zones.shp"), output_dir=str(tmp_path / "out"))
    assert result["status"] == "error"
    assert "polyconvert failed (exit code 1)" in result["message"]
    assert "Error: the real reason it failed." in result["message"]


@needs_sumo
def test_netconvert_real_error_includes_stderr(tmp_path):
    osm = tmp_path / "broken.osm"
    osm.write_text("<osm><node id='1' lat='x'/></osm>")
    result = NetConverter().convert(str(osm), city_en="broken", output_dir=str(tmp_path / "out"))
    assert result["status"] == "error"
    assert "Error:" in result["message"]
