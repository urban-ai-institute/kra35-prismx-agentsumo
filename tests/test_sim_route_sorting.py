"""
Tests for keeping route files sorted when vehicles/flows are added:
SUMO drops anything departing before an element it has already read
("Route file should be sorted by departure time, ignoring ...").

1. sort_by_departure() with mixed and non-numeric elements
2. vehicle_generation / flow_generation insert at the departure time
3. Real SUMO run (skipped without SUMO): the added vehicles and flow depart
"""

from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.customization import vehicle_manager as vm_module
from agentsumo_mcp.customization.vehicle_manager import (
    VehicleManager, _parse_time, sort_by_departure
)
from agentsumo_mcp.settings.settings import sumo_environment

SUMO_BIN = Path(sumo_environment.get_binary_path("sumo"))
needs_sumo = pytest.mark.skipif(not SUMO_BIN.exists(), reason=f"SUMO not installed ({SUMO_BIN})")

# Two edges in a row, "a" (Src Road) -> "b" (Dst Road); enough for sumolib
TINY_NET = """<net version="1.20">
    <location netOffset="0.00,0.00" convBoundary="0.00,0.00,200.00,0.00" origBoundary="0.00,0.00,200.00,0.00" projParameter="!"/>
    <edge id="a" from="J0" to="J1" name="Src Road">
        <lane id="a_0" index="0" speed="13.89" length="100.00" shape="0.00,-1.60 100.00,-1.60"/>
    </edge>
    <edge id="b" from="J1" to="J2" name="Dst Road">
        <lane id="b_0" index="0" speed="13.89" length="100.00" shape="100.00,-1.60 200.00,-1.60"/>
    </edge>
    <junction id="J0" type="dead_end" x="0.00" y="0.00" incLanes="" intLanes="" shape="0.00,0.00 0.00,-3.20"/>
    <junction id="J1" type="priority" x="100.00" y="0.00" incLanes="a_0" intLanes="" shape="100.00,0.00 100.00,-3.20"/>
    <junction id="J2" type="dead_end" x="200.00" y="0.00" incLanes="b_0" intLanes="" shape="200.00,-3.20 200.00,0.00"/>
    <connection from="a" to="b" fromLane="0" toLane="0" dir="s" state="M"/>
</net>
"""

ROUTES = """<routes>
    <vType id="passenger"/>
    <vehicle id="v0" type="passenger" depart="0.00"><route edges="{e1} {e2}"/></vehicle>
    <vehicle id="v50" type="passenger" depart="50.00"><route edges="{e1} {e2}"/></vehicle>
    <vehicle id="v100" type="passenger" depart="100.00"><route edges="{e1} {e2}"/></vehicle>
</routes>
"""


def _ids(path_or_root):
    root = path_or_root if isinstance(path_or_root, ET.Element) else ET.parse(path_or_root).getroot()
    return [child.get("id") for child in root]


def test_sort_by_departure_with_mixed_elements():
    root = ET.fromstring("""<routes>
        <vType id="passenger"/>
        <route id="r0" edges="a b"/>
        <vehicle id="v0" depart="0.00" route="r0"/>
        <vehicle id="v100" depart="100.00" route="r0"/>
        <vehicle id="bus" depart="triggered" route="r0"/>
        <flow id="old_flow" begin="200" end="300" number="5" route="r0"/>
        <trip id="hms" depart="1:00:00" from="a" to="b"/>
        <vehicle id="new0" depart="0.0" route="r0"/>
        <flow id="new_flow" begin="50" end="60" number="2" route="r0"/>
        <route id="r1" edges="a"/>
        <person id="p_now" depart="now"><walk edges="a"/></person>
        <flow id="no_begin" end="10" number="1" route="r0"/>
    </routes>""")

    sort_by_departure(root)

    assert _ids(root) == [
        # definitions first, in their original order
        "passenger", "r0", "r1",
        # flows without begin start at the simulation begin (0)
        "v0", "new0", "no_begin",
        # non-numeric departures stay right after their predecessor
        "new_flow", "p_now",
        "v100", "bus",
        "old_flow",
        "hms",
    ]
    # nested content is untouched
    assert root.find("person/walk").get("edges") == "a"


def test_sort_by_departure_keeps_sorted_file_unchanged():
    root = ET.fromstring(ROUTES.format(e1="a", e2="b"))

    sort_by_departure(root)

    assert _ids(root) == ["passenger", "v0", "v50", "v100"]


@pytest.mark.parametrize("value, seconds", [
    ("12.5", 12.5), ("0", 0.0), ("1:00:00", 3600.0), ("1:00:00:30", 86430.0),
    ("triggered", None), ("containerTriggered", None), ("now", None), ("begin", None),
    ("nan", None), (None, None),
])
def test_parse_time(value, seconds):
    assert _parse_time(value) == seconds


@pytest.fixture
def tiny_inputs(tmp_path):
    net = tmp_path / "tiny.net.xml"
    net.write_text(TINY_NET)
    routes = tmp_path / "base.rou.xml"
    routes.write_text(ROUTES.format(e1="a", e2="b"))
    return str(net), str(routes)


def test_generated_vehicles_are_inserted_by_departure(tmp_path, tiny_inputs):
    net, routes = tiny_inputs

    result = VehicleManager().generate_vehicles(
        route_file=routes, net_file=net, source_location="Src Road",
        destination_location="Dst Road", vehicle_id="gen", depart_time=0.0,
        vehicle_count=3, output_dir=str(tmp_path / "out"),
    )

    assert result["status"] == "success", result["message"]
    # departures 0, 10, 20 go between v0 and v50
    assert _ids(result["route_file"]) == ["passenger", "v0", "gen_0", "gen_1", "gen_2", "v50", "v100"]


def _patch_coordinate_lookup(monkeypatch, source_edge, dest_edge):
    monkeypatch.setattr(vm_module, "check_coordinates_in_network", lambda *a, **k: (True, {}))
    monkeypatch.setattr(
        vm_module, "find_nearest_edge",
        lambda net_file, lat, lon, radius: (source_edge if lat == 1.0 else dest_edge, 0.0),
    )


def test_generated_flow_is_inserted_by_begin(tmp_path, tiny_inputs, monkeypatch):
    net, routes = tiny_inputs
    _patch_coordinate_lookup(monkeypatch, "a", "b")

    result = VehicleManager().generate_flow(
        route_file=routes, net_file=net, source_lat=1.0, source_lon=0.0,
        dest_lat=2.0, dest_lon=0.0, begin=60.0, end=120.0, number=3,
        flow_id="f", output_dir=str(tmp_path / "out"),
    )

    assert result["status"] == "success", result["message"]
    assert _ids(result["route_file"]) == ["passenger", "v0", "v50", "f", "v100"]


# ---------------------------------------------------------------- real SUMO

@needs_sumo
def test_added_vehicles_and_flow_depart_in_sumo(tmp_path, monkeypatch):
    net = tmp_path / "grid.net.xml"
    subprocess.run(
        [str(SUMO_BIN.with_name("netgenerate")), "--grid", "--grid.number", "3",
         "--grid.length", "100", "-o", str(net)],
        check=True, capture_output=True,
    )
    base = tmp_path / "base.rou.xml"
    base.write_text(ROUTES.format(e1="A0A1", e2="A1A2"))
    out = str(tmp_path / "out")

    monkeypatch.setattr(
        vm_module, "get_edge_ids_from_road_name",
        lambda net_file, name: {"src": ["A0A1"], "dst": ["A1A2"]}[name],
    )
    _patch_coordinate_lookup(monkeypatch, "A0A1", "A1A2")
    manager = VehicleManager()
    vehicles = manager.generate_vehicles(
        route_file=str(base), net_file=str(net), source_location="src",
        destination_location="dst", vehicle_id="gen", vehicle_count=3, output_dir=out,
    )
    flow = manager.generate_flow(
        route_file=vehicles["route_file"], net_file=str(net), source_lat=1.0, source_lon=0.0,
        dest_lat=2.0, dest_lon=0.0, begin=0.0, end=100.0, number=4, flow_id="f", output_dir=out,
    )
    assert flow["status"] == "success", flow["message"]

    tripinfo = tmp_path / "tripinfo.xml"
    sumo = subprocess.run(
        [str(SUMO_BIN), "-n", str(net), "-r", flow["route_file"], "--end", "1000",
         "--tripinfo-output", str(tripinfo), "--no-step-log"],
        capture_output=True, text=True,
    )

    assert sumo.returncode == 0, sumo.stderr
    assert "sorted" not in sumo.stdout + sumo.stderr
    departed = _ids(tripinfo)
    assert {"v0", "v50", "v100", "gen_0", "gen_1", "gen_2"} <= set(departed)
    assert sum(i.startswith("f.") for i in departed) == 4
