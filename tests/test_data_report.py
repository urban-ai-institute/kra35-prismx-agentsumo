"""
Tests for simulation_report_tool (no SUMO binary needed):
1. Fuel is reported in kg (SUMO writes fuel_abs in mg), not mislabelled "L"
2. An unreadable net_file does not crash the report (module logger exists)
"""

import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import agentsumo_mcp.main as server
from agentsumo_mcp.analysis.xml_to_sqlite import XMLToSQLiteConverter

from test_data_xml_to_sqlite import _write_inputs


def _import(f, db, trip="trip2", net=None, **kw):
    result = XMLToSQLiteConverter().convert_simulation_results(
        tripinfo_xml=f[trip], edgedata_xml=f["edge"], edgedata_emission_xml=f["emis"],
        output_db=str(db), net_file=net or f["net"], summary_xml=f["summ"], **kw
    )
    assert result["status"] == "success", result
    return result


def _report(tmp_path, db):
    return server.simulation_report_tool(
        db_path=str(db), executive_summary="summary", output_dir=str(tmp_path / "reports")
    )


def _cells(html, label):
    row = re.search(rf"<td[^>]*>{re.escape(label)}</td>(.*?)</tr>", html, re.S).group(1)
    return re.findall(r"<td[^>]*>([^<]*)</td>", row)


def test_fuel_is_reported_in_kg(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    _import(f, db, simulation_id="1_baseline", description="Baseline")

    result = _report(tmp_path, db)
    assert result["status"] == "success", result
    html = Path(result["report_file"]).read_text(encoding="utf-8")
    # 2 trips x 10000 mg fuel = 0.02 kg
    assert _cells(html, "Total Fuel") == ["0.02 kg"]
    assert " L<" not in html


def test_unreadable_net_file_does_not_crash(tmp_path):
    f = _write_inputs(tmp_path)
    db = tmp_path / "a.db"
    _import(f, db, net=str(tmp_path / "missing.net.xml"), simulation_id="1_baseline", description="Baseline")

    result = _report(tmp_path, db)
    assert result["status"] == "success", result
