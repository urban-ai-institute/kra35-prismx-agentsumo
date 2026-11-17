"""
Tests for sumo_runner (SimulationRunner):
1. sumocfg generation for route- and trip-only input
2. Result shape: failures are errors and only existing output files are returned
3. Real SUMO runs (skipped without SUMO): broken input fails fast with SUMO's message
"""

from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.baseline.simulation_runner import SimulationRunner
from agentsumo_mcp.settings.settings import sumo_environment


OUTPUT_FILES = SimulationRunner()._generate_output_filenames("net", "ts")

SUMO_BIN = Path(sumo_environment.get_binary_path("sumo"))
needs_sumo = pytest.mark.skipif(not SUMO_BIN.exists(), reason=f"SUMO not installed ({SUMO_BIN})")

GOOD_ROUTES = """<routes>
    <trip id="t0" type="passenger" depart="0" from="A0A1" to="A1A2"/>
    <trip id="t1" type="passenger" depart="5" from="A0B0" to="B0C0"/>
</routes>
"""
BROKEN_ROUTES = """<routes>
    <vehicle id="v0" type="passenger" depart="0"><route edges="NO_SUCH_EDGE"/></vehicle>
</routes>
"""


def _input_options(tmp_path, route_file, trip_file):
    cfg = SimulationRunner()._generate_config_file(
        tmp_path,
        {"net_file": "net.net.xml", "route_file": route_file, "trip_file": trip_file},
        [], "additional.add.xml", OUTPUT_FILES, 600, "ts",
    )
    return {child.tag: child.get("value") for child in ET.parse(cfg).getroot().find("input")}


def test_trip_only_input_is_loaded_as_route_files(tmp_path):
    options = _input_options(tmp_path, None, "net.trips.xml")

    assert options["route-files"] == "net.trips.xml"
    assert "trip-files" not in options


def test_route_file_is_preferred_over_trip_file(tmp_path):
    options = _input_options(tmp_path, "net.rou.xml", "net.trips.xml")

    assert options["route-files"] == "net.rou.xml"


class _Result:
    def __init__(self, returncode, stderr="", replay_file=None, sumo_log=None):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr
        self.elapsed = 1.0
        self.replay_file = replay_file
        self.sumo_log = sumo_log


def test_failed_run_is_an_error_without_output_paths(tmp_path):
    # Even if SUMO left (partial) files behind, a failed run hands out none
    (tmp_path / OUTPUT_FILES["tripinfo"]).write_text("<tripinfos>")
    stderr = "Error: The edge 'x' within the route for vehicle 'v0' is not known."

    result = SimulationRunner()._prepare_result(
        _Result(1, stderr, sumo_log=str(tmp_path / "net_sumo_ts.log")),
        tmp_path, OUTPUT_FILES, tmp_path, 600,
    )

    assert result["status"] == "error"
    assert result["output_files"] == []
    assert result["summary_xml"] is None
    assert stderr in result["message"]
    assert result["sumo_log"] == str(tmp_path / "net_sumo_ts.log")


def test_successful_run_returns_only_existing_files(tmp_path):
    (tmp_path / OUTPUT_FILES["tripinfo"]).write_text("<tripinfos/>")

    result = SimulationRunner()._prepare_result(
        _Result(0), tmp_path, OUTPUT_FILES, tmp_path, 600,
    )

    assert result["status"] == "success"
    assert result["output_files"] == [str(tmp_path / OUTPUT_FILES["tripinfo"])]
    assert result["summary_xml"] is None
    assert result["metadata"]["absolute_summary"] is None


# ---------------------------------------------------------------- real SUMO

@pytest.fixture
def grid_net(tmp_path):
    net = tmp_path / "grid.net.xml"
    subprocess.run(
        [str(SUMO_BIN.with_name("netgenerate")), "--grid", "--grid.number", "3",
         "--grid.length", "100", "-o", str(net)],
        check=True, capture_output=True,
    )
    return net


def _route_file(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return str(path)


@needs_sumo
def test_broken_input_fails_fast_with_sumo_error(tmp_path, grid_net):
    route_file = _route_file(tmp_path, "broken.rou.xml", BROKEN_ROUTES)

    start = time.time()
    result = SimulationRunner().run(
        net_file=str(grid_net), route_file=route_file, duration=60,
        output_dir=str(tmp_path / "sim"),
    )
    elapsed = time.time() - start

    assert result["status"] == "error"
    assert elapsed < 10, f"took {elapsed:.1f}s"
    assert "NO_SUCH_EDGE" in result["message"]
    assert result["output_files"] == []
    assert result["summary_xml"] is None
    assert "NO_SUCH_EDGE" in Path(result["sumo_log"]).read_text()


@needs_sumo
def test_successful_run_returns_existing_outputs(tmp_path, grid_net):
    route_file = _route_file(tmp_path, "good.rou.xml", GOOD_ROUTES)

    result = SimulationRunner().run(
        net_file=str(grid_net), route_file=route_file, duration=120,
        output_dir=str(tmp_path / "sim"),
    )

    assert result["status"] == "success", result["message"]
    assert len(result["output_files"]) == 3
    assert all(Path(p).exists() for p in result["output_files"])
    assert Path(result["summary_xml"]).exists()
    assert len(ET.parse(result["output_files"][0]).getroot().findall("tripinfo")) == 2
