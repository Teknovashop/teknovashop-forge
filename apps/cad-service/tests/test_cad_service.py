from pathlib import Path
import tempfile

import cadquery as cq

from app import (
    CadOperation,
    PlateDesignRequest,
    PlateRequest,
    build_plate,
    build_plate_design,
    health,
)


def test_health_exposes_cadquery_engine():
    payload = health()
    assert payload["ok"] is True
    assert payload["engine"] == "cadquery"
    assert payload["cadquery_version"]
    assert "vent_hex" in payload["operations"]
    assert "cable_channel" in payload["operations"]


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



def test_cad_operation_stack_builds_valid_brep():
    design = PlateDesignRequest(
        width=140,
        height=100,
        thickness=8,
        corner_radius=6,
        chamfer=1,
        operations=[
            CadOperation(type="hole", x=-35, y=-20, diameter_mm=6),
            CadOperation(type="slot", x=25, y=-20, length_mm=24, width_mm=6),
            CadOperation(type="cutout_rect", x=0, y=18, width_mm=24, height_mm=14),
            CadOperation(
                type="counterbore",
                x=35,
                y=24,
                through_diameter_mm=5,
                bore_diameter_mm=10,
                bore_depth_mm=2,
            ),
            CadOperation(type="pocket_rect", x=-30, y=24, width_mm=18, height_mm=12, depth_mm=1.5),
            CadOperation(type="boss", x=0, y=-30, diameter_mm=14, height_mm=4),
        ],
    )
    result = build_plate_design(design)
    solid = result.val()
    assert solid.isValid()
    assert solid.Volume() > 0


def test_cad_vesa_pattern_creates_four_through_holes():
    base = build_plate(
        PlateRequest(width=140, height=140, thickness=8, corner_radius=4, chamfer=1)
    )
    result = build_plate_design(
        PlateDesignRequest(
            width=140,
            height=140,
            thickness=8,
            corner_radius=4,
            chamfer=1,
            operations=[
                CadOperation(type="vesa_pattern", pitch_mm=75, diameter_mm=5)
            ],
        )
    )
    assert result.val().isValid()
    assert result.val().Volume() < base.val().Volume()


def test_cad_operation_stack_exports_stl_and_step():
    result = build_plate_design(
        PlateDesignRequest(
            operations=[
                CadOperation(type="hole", x=15, y=0, diameter_mm=5),
                CadOperation(type="cutout_circle", x=-15, y=0, diameter_mm=10),
            ]
        )
    )
    with tempfile.TemporaryDirectory() as td:
        stl = Path(td) / "design.stl"
        step = Path(td) / "design.step"
        cq.exporters.export(result, str(stl), exportType="STL")
        cq.exporters.export(result, str(step), exportType="STEP")
        assert stl.stat().st_size > 100
        assert step.stat().st_size > 100


def test_unsupported_cad_operation_fails_closed():
    import pytest

    with pytest.raises(ValueError, match="Unsupported CAD operation"):
        build_plate_design(
            PlateDesignRequest(
                operations=[CadOperation(type="future_magic")]
            )
        )



def test_cad_patterns_and_vents_keep_valid_brep():
    result = build_plate_design(
        PlateDesignRequest(
            width=180,
            height=130,
            thickness=8,
            corner_radius=5,
            chamfer=1,
            operations=[
                CadOperation(
                    type="hole_pattern",
                    x=-45,
                    y=15,
                    diameter_mm=4,
                    rows=2,
                    cols=3,
                    spacing_x_mm=14,
                    spacing_y_mm=14,
                ),
                CadOperation(
                    type="vent_linear",
                    x=35,
                    y=-20,
                    count=4,
                    length_mm=30,
                    width_mm=3,
                    spacing_mm=8,
                ),
                CadOperation(
                    type="vent_hex",
                    x=30,
                    y=28,
                    rows=2,
                    cols=3,
                    radius_mm=3,
                    gap_mm=2,
                ),
            ],
        )
    )
    solid = result.val()
    assert solid.isValid()
    assert solid.Volume() > 0


def test_cad_channel_removes_material_and_rib_adds_material():
    base = build_plate(
        PlateRequest(width=150, height=100, thickness=8, corner_radius=4, chamfer=1)
    )
    channel = build_plate_design(
        PlateDesignRequest(
            width=150,
            height=100,
            thickness=8,
            corner_radius=4,
            chamfer=1,
            operations=[
                CadOperation(
                    type="cable_channel",
                    x=0,
                    y=0,
                    length_mm=45,
                    width_mm=9,
                )
            ],
        )
    )
    rib = build_plate_design(
        PlateDesignRequest(
            width=150,
            height=100,
            thickness=8,
            corner_radius=4,
            chamfer=1,
            operations=[
                CadOperation(
                    type="rib",
                    x=0,
                    y=0,
                    length_mm=55,
                    width_mm=5,
                    height_mm=4,
                    rotation_deg=15,
                )
            ],
        )
    )

    assert channel.val().isValid()
    assert rib.val().isValid()
    assert channel.val().Volume() < base.val().Volume()
    assert rib.val().Volume() > base.val().Volume()
