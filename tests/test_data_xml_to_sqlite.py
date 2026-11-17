"""
Tests for XMLToSQLiteConverter (no SUMO binary needed):
1. An explicit simulation_id that exists is replaced in every table
2. No simulation_id -> a new unique auto id; other simulations are never touched
3. A 0-byte DB file gets the schema instead of failing with "no such table"
4. edgedata attributes SUMO did not write are stored as NULL, not 0.0
"""

import datetime as real_datetime
import sqlite3
import sys
import types
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import agentsumo_mcp.analysis.xml_to_sqlite as x2s
from agentsumo_mcp.analysis.xml_to_sqlite import XMLToSQLiteConverter

TABLES = ["simulations", "trips", "vehicle_info", "edge_info", "edge_metrics", "network_state"]

NET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.20" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <location netOffset="0.00,0.00" convBoundary="0.00,0.00,200.00,0.00" origBoundary="0.00,0.00,200.00,0.00" projParameter="!"/>
    <edge id="e1" from="A" to="B" priority="1" name="Main St">
        <lane id="e1_0" index="0" speed="13.89" length="100.00" shape="0.00,-1.60 100.00,-1.60"/>
    </edge>
    <edge id="e2" from="B" to="C" priority="1" name="Main St">
        <lane id="e2_0" index="0" speed="13.89" length="100.00" shape="100.00,-1.60 200.00,-1.60"/>
    </edge>
    <edge id="e3" from="C" to="B" priority="1" name="Side St">
        <lane id="e3_0" index="0" speed="8.33" length="100.00" shape="200.00,1.60 100.00,1.60"/>
    </edge>
    <junction id="A" type="dead_end" x="0.00" y="0.00" incLanes="" intLanes="" shape="0.00,0.00 0.00,-3.20"/>
    <junction id="B" type="priority" x="100.00" y="0.00" incLanes="e1_0 e3_0" intLanes="" shape="100.00,3.20 100.00,-3.20"/>
    <junction id="C" type="dead_end" x="200.00" y="0.00" incLanes="e2_0" intLanes="" shape="200.00,-3.20 200.00,3.20"/>
</net>
"""


def _tripinfo(n_trips):
    rows = []
    for i in range(n_trips):
        rows.append(
            f'<tripinfo id="v{i}" depart="{i}.00" departLane="e1_0" departPos="5.00" departSpeed="10.00" '
            f'departDelay="0.00" arrival="{20 + i}.00" arrivalLane="e2_0" arrivalPos="95.00" arrivalSpeed="10.00" '
            f'duration="20.00" routeLength="190.00" waitingTime="0.00" waitingCount="0" stopTime="0.00" '
            f'timeLoss="3.00" rerouteNo="0" devices="tripinfo_v{i} emissions_v{i}" vType="passenger" '
            f'speedFactor="1.00" vaporized="">'
            f'<emissions CO_abs="100.00" CO2_abs="31350.00" HC_abs="1.00" PMx_abs="0.50" NOx_abs="10.00" '
            f'fuel_abs="10000.00" electricity_abs="0.00"/></tripinfo>'
        )
    return "<tripinfos>\n" + "\n".join(rows) + "\n</tripinfos>\n"


# e1/e2 used; e3 idle -> SUMO writes only sampledSeconds and the counters.
EDGEDATA_XML = """<meandata>
    <interval begin="0.00" end="600.00" id="dump_output">
        <edge id="e1" sampledSeconds="20.00" traveltime="8.00" overlapTraveltime="9.00" density="0.50" laneDensity="0.50" occupancy="0.25" waitingTime="0.00" timeLoss="1.00" speed="12.00" speedRelative="0.86" departed="2" arrived="0" entered="0" left="2" laneChangedFrom="0" laneChangedTo="0"/>
        <edge id="e2" sampledSeconds="20.00" traveltime="10.00" overlapTraveltime="11.00" density="0.50" laneDensity="0.50" occupancy="0.25" waitingTime="2.00" timeLoss="2.00" speed="8.00" speedRelative="0.58" departed="0" arrived="2" entered="2" left="0" laneChangedFrom="0" laneChangedTo="0"/>
        <edge id="e3" sampledSeconds="0.00" departed="0" arrived="0" entered="0" left="0" laneChangedFrom="0" laneChangedTo="0"/>
    </interval>
</meandata>
"""

# excludeEmpty="true": the idle edge e3 is not in the file at all.
EMISSION_XML = """<meandata>
    <interval begin="0.00" end="600.00" id="dump_output_emission">
        <edge id="e1" sampledSeconds="20.00" CO_abs="50.00" CO2_abs="15000.00" HC_abs="0.50" PMx_abs="0.25" NOx_abs="5.00" fuel_abs="5000.00" electricity_abs="0.00"/>
        <edge id="e2" sampledSeconds="20.00" CO_abs="50.00" CO2_abs="16350.00" HC_abs="0.50" PMx_abs="0.25" NOx_abs="5.00" fuel_abs="5000.00" electricity_abs="0.00"/>
    </interval>
</meandata>
"""

SUMMARY_XML = """<summary>
    <step time="0.00" loaded="2" inserted="1" running="1" waiting="0" ended="0" arrived="0" collisions="0" teleports="0" halting="0" stopped="0" meanWaitingTime="0.00" meanTravelTime="-1.00" meanSpeed="10.00" meanSpeedRelative="0.72" duration="1"/>
    <step time="1.00" loaded="2" inserted="2" running="2" waiting="0" ended="0" arrived="0" collisions="0" teleports="0" halting="0" stopped="0" meanWaitingTime="0.00" meanTravelTime="-1.00" meanSpeed="10.00" meanSpeedRelative="0.72" duration="1"/>
</summary>
"""


def _write_inputs(tmp_path):
    files = {
        "net": ("x.net.xml", NET_XML),
        "trip2": ("x_tripinfo_2.xml", _tripinfo(2)),
        "trip1": ("x_tripinfo_1.xml", _tripinfo(1)),
        "trip0": ("x_tripinfo_0.xml", _tripinfo(0)),
        "edge": ("x_netstate.xml", EDGEDATA_XML),
        "emis": ("x_netstate_emission.xml", EMISSION_XML),
        "summ": ("x_summary.xml", SUMMARY_XML),
    }
    out = {}
    for key, (name, content) in files.items():
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        out[key] = str(p)
    return out


def _import(f, db, trip="trip2", **kw):
    return XMLToSQLiteConverter().convert_simulation_results(
        tripinfo_xml=f[trip], edgedata_xml=f["edge"], edgedata_emission_xml=f["emis"],
        output_db=str(db), net_file=f["net"], summary_xml=f["summ"], **kw
    )


def _counts(db):
    con = sqlite3.connect(db)
    try:
        return {
            t: dict(con.execute(f"SELECT simulation_id, COUNT(*) FROM {t} GROUP BY 1").fetchall())
            for t in TABLES
        }
    finally:
        con.close()


def test_explicit_id_that_exists_is_replaced_in_every_table(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"

    first = _import(f, db, simulation_id="1_baseline", description="old")
    assert first["status"] == "success" and first["replaced"] is False

    # A new chat restarts numbering at 1_baseline: the new results must win.
    second = _import(f, db, trip="trip1", simulation_id="1_baseline", description="new")
    assert second["status"] == "success"
    assert second["simulation_id"] == "1_baseline"
    assert second["replaced"] is True
    assert "Replaced" in second["message"]

    counts = _counts(db)
    assert counts["simulations"] == {"1_baseline": 1}
    assert counts["trips"] == {"1_baseline": 1}
    assert counts["vehicle_info"] == {"1_baseline": 1}
    assert counts["edge_info"] == {"1_baseline": 3}
    assert counts["edge_metrics"] == {"1_baseline": 3}
    assert counts["network_state"] == {"1_baseline": 2}

    con = sqlite3.connect(db)
    assert con.execute("SELECT description, vehicle_count FROM simulations").fetchone() == ("new", 1)
    con.close()


def test_auto_id_never_reuses_or_skips_named_simulation(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    _import(f, db, simulation_id="1_baseline", description="baseline")

    auto = _import(f, db, simulation_id=None)
    assert auto["status"] == "success"
    assert auto["simulation_id"] not in ("1_baseline", None)
    assert auto["simulation_id"].startswith("sim_")

    counts = _counts(db)
    for t in TABLES:
        assert set(counts[t]) == {"1_baseline", auto["simulation_id"]}, t


def test_named_import_does_not_delete_auto_simulation_on_same_net(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    auto = _import(f, db, simulation_id=None)
    named = _import(f, db, simulation_id="2_ev_50pct", description="EV 50%")
    assert named["status"] == "success" and named["replaced"] is False

    counts = _counts(db)
    for t in TABLES:
        assert set(counts[t]) == {auto["simulation_id"], "2_ev_50pct"}, t


def test_auto_ids_are_unique_within_the_same_millisecond(tmp_path, monkeypatch):
    fixed = real_datetime.datetime(2026, 1, 2, 3, 4, 5, 6000)

    class FrozenDateTime(real_datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(x2s, "datetime", types.SimpleNamespace(datetime=FrozenDateTime))

    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    ids = [_import(f, db, simulation_id=None)["simulation_id"] for _ in range(3)]
    assert ids == ["sim_20260102_030405_006", "sim_20260102_030405_006_2", "sim_20260102_030405_006_3"]
    assert set(_counts(db)["trips"]) == set(ids)


def test_failed_replace_keeps_previous_rows(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    _import(f, db, simulation_id="1_baseline", description="old")

    bad = XMLToSQLiteConverter().convert_simulation_results(
        tripinfo_xml=str(tmp_path / "missing_tripinfo.xml"), edgedata_xml=f["edge"],
        edgedata_emission_xml=f["emis"], output_db=str(db), simulation_id="1_baseline",
        net_file=f["net"], description="new",
    )
    assert bad["status"] == "error"

    counts = _counts(db)
    assert counts["trips"] == {"1_baseline": 2}
    assert counts["edge_info"] == {"1_baseline": 3}
    con = sqlite3.connect(db)
    assert con.execute("SELECT description FROM simulations").fetchone() == ("old",)
    con.close()


def test_zero_byte_db_file_gets_schema(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "empty.db"
    db.write_bytes(b"")  # what sqlite3.connect() leaves behind for a wrong path

    result = _import(f, db, simulation_id="1_baseline", description="d")
    assert result["status"] == "success", result
    assert _counts(db)["trips"] == {"1_baseline": 2}


def test_older_db_missing_new_tables_is_migrated(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "old.db"
    _import(f, db, simulation_id="1_baseline", description="d")
    con = sqlite3.connect(db)
    for t in ("vehicle_info", "edge_info", "network_state"):
        con.execute(f"DROP TABLE {t}")
    con.commit()
    con.close()

    result = _import(f, db, simulation_id="2_policy", description="p")
    assert result["status"] == "success", result
    counts = _counts(db)
    assert counts["edge_info"] == {"2_policy": 3}
    assert set(counts["trips"]) == {"1_baseline", "2_policy"}


def test_unwritten_edgedata_attributes_are_null(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    _import(f, db, simulation_id="1_baseline", description="d")

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    idle = con.execute("SELECT * FROM edge_metrics WHERE edge_id='e3'").fetchone()
    for col in ("traveltime", "overlapTraveltime", "density", "occupancy", "waitingTime",
                "timeLoss", "speed", "speedRelative", "CO2_abs", "fuel_abs", "CO2_perVeh"):
        assert idle[col] is None, col
    # Attributes SUMO did write keep their value, including real zeros.
    assert idle["sampledSeconds"] == 0.0
    assert idle["entered"] == 0 and idle["left"] == 0

    used = con.execute("SELECT * FROM edge_metrics WHERE edge_id='e1'").fetchone()
    assert used["speed"] == 12.0 and used["CO2_abs"] == 15000.0

    # AVG() over the used edges only, and the slowest edge is a used one.
    assert con.execute("SELECT AVG(speed) FROM edge_metrics").fetchone()[0] == 10.0
    slowest = con.execute(
        "SELECT edge_id FROM edge_metrics WHERE speed IS NOT NULL ORDER BY speed LIMIT 1"
    ).fetchone()[0]
    assert slowest == "e2"
    assert con.execute("SELECT SUM(CO2_abs) FROM edge_metrics").fetchone()[0] == 31350.0
    con.close()
