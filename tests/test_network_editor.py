"""
Tests for network editing (requires a local SUMO; skipped otherwise):
1. reduce_lanes recomputes only the junctions the modified edges touch
   and keeps every edge-to-edge movement there
2. Edits that change nothing report an error instead of success
"""

import os
import subprocess
from pathlib import Path
import sys

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentsumo_mcp.settings.settings import sumo_environment

NETGENERATE = sumo_environment.get_binary_path("netgenerate")
pytestmark = pytest.mark.skipif(
    not (os.path.exists(NETGENERATE) or os.path.exists(NETGENERATE + ".exe")),
    reason="SUMO is not installed"
)


@pytest.fixture
def grid_net(tmp_path):
    """4x4 two-lane grid with traffic lights and one turn restriction.

    The left turn C2B2 -> B2B3 is removed, like an OSM no_left_turn
    relation: a rebuild that re-guesses connections would bring it back.
    """
    plain_net = tmp_path / "plain.net.xml"
    subprocess.run([
        NETGENERATE, "--grid", "--grid.number", "4", "--grid.length", "200",
        "--default.lanenumber", "2", "--tls.guess", "true", "-o", str(plain_net)
    ], check=True, capture_output=True)
    restriction = tmp_path / "restriction.con.xml"
    restriction.write_text('<connections>\n    <delete from="C2B2" to="B2B3"/>\n</connections>\n')
    net_file = tmp_path / "grid.net.xml"
    subprocess.run([
        sumo_environment.get_binary_path("netconvert"), "-s", str(plain_net),
        "-x", str(restriction), "-o", str(net_file)
    ], check=True, capture_output=True)
    return net_file


def _connections(net):
    by_junction = {}
    for edge in net.getEdges():
        for conns in edge.getOutgoing().values():
            for c in conns:
                by_junction.setdefault(edge.getToNode().getID(), set()).add(
                    (c.getFrom().getID(), c.getTo().getID(), c.getFromLane().getIndex(), c.getToLane().getIndex())
                )
    return by_junction


def test_reduce_lanes_only_recomputes_touched_junctions(grid_net, tmp_path):
    import sumolib
    from agentsumo_mcp.customization.network_editor import NetworkEditor

    orig = sumolib.net.readNet(str(grid_net), withConnections=True)
    assert not orig.getEdge("C2B2").getConnections(orig.getEdge("B2B3"))
    # Far from the restricted junction B2
    target = orig.getEdge("D0D1")
    touched = {target.getFromNode().getID(), target.getToNode().getID()}

    result = NetworkEditor().reduce_lanes(
        net_file=str(grid_net), output_dir=str(tmp_path / "out"), edge_ids=[target.getID()], reduce_by=1
    )
    assert result["status"] == "success", result

    new = sumolib.net.readNet(result["net_file"], withConnections=True)
    assert new.getEdge(target.getID()).getLaneNumber() == 1

    before, after = _connections(orig), _connections(new)
    for junction in set(before) | set(after):
        if junction in touched:
            # Same movements, lanes reassigned
            assert {(f, t) for f, t, _, _ in before[junction]} == {(f, t) for f, t, _, _ in after[junction]}
        else:
            assert before.get(junction) == after.get(junction), junction

    for conns in after.values():
        for f, t, from_lane, to_lane in conns:
            assert from_lane < new.getEdge(f).getLaneNumber()
            assert to_lane < new.getEdge(t).getLaneNumber()


def test_edits_that_change_nothing_are_errors(grid_net, tmp_path):
    from agentsumo_mcp.customization.network_editor import NetworkEditor

    editor = NetworkEditor()
    out = str(tmp_path / "out")
    assert editor.reduce_lanes(net_file=str(grid_net), output_dir=out, edge_ids=["missing"], reduce_by=1)["status"] == "error"
    assert editor.edit_edge(net_file=str(grid_net), output_dir=out, edge_ids=["missing"])["status"] == "error"
    assert editor.edit_speed_limit(net_file=str(grid_net), output_dir=out, edge_ids=["missing"], new_speed_kmph=30)["status"] == "error"
