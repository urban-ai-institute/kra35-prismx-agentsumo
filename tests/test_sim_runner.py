"""
Tests for sumo_runner (SimulationRunner):
1. sumocfg generation for route- and trip-only input
"""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.baseline.simulation_runner import SimulationRunner


OUTPUT_FILES = SimulationRunner()._generate_output_filenames("net", "ts")


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
