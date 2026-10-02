from pathlib import Path
import tempfile

import cadquery as cq

from app import PlateRequest, build_plate, health


def test_health_exposes_cadquery_engine():
    payload = health()
    assert payload["ok"] is True
    assert payload["engine"] == "cadquery"
    assert payload["cadquery_version"]


def test_plate_builds_valid_brep_with_fillets_and_chamfer():
    result = build_plate(
        PlateRequest(
            width=120,
            height=80,
            thickness=8,
            corner_radius=5,
            chamfer=1,
        )
    )
    solid = result.val()
    assert solid.isValid()
    assert solid.Volume() > 0


def test_plate_exports_stl_and_step():
    result = build_plate(PlateRequest())
    with tempfile.TemporaryDirectory() as td:
        stl = Path(td) / "plate.stl"
        step = Path(td) / "plate.step"
        cq.exporters.export(result, str(stl), exportType="STL")
        cq.exporters.export(result, str(step), exportType="STEP")
        assert stl.stat().st_size > 100
        assert step.stat().st_size > 100
