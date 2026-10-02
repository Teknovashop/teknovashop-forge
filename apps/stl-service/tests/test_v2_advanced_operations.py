from __future__ import annotations

import pytest

from model_contracts import PRODUCTS
from models import REGISTRY
from v2_operations import apply_operations, validate_operations


CASES = [
    {
        "id": "grid",
        "type": "hole_pattern",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0},
        "params": {"diameter_mm": 4, "rows": 2, "cols": 2, "spacing_x_mm": 18, "spacing_y_mm": 18},
    },
    {
        "id": "vents",
        "type": "vent_linear",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0, "rotation_deg": 0},
        "params": {"count": 4, "length_mm": 30, "width_mm": 3, "spacing_mm": 7},
    },
    {
        "id": "hex",
        "type": "vent_hex",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": -25, "y": 0},
        "params": {"rows": 2, "cols": 3, "radius_mm": 3, "gap_mm": 2},
    },
    {
        "id": "channel",
        "type": "cable_channel",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0, "rotation_deg": 0},
        "params": {"length_mm": 26, "width_mm": 5},
    },
]


@pytest.mark.parametrize("operation", CASES, ids=[x["type"] for x in CASES])
def test_advanced_subtractive_operations_are_watertight(operation):
    contract = PRODUCTS["enclosure-ip65"]
    mesh = REGISTRY[contract["builder"]](dict(contract["default"]))
    result = apply_operations(mesh, "enclosure-ip65", [operation])
    assert result.is_watertight
    assert result.is_winding_consistent
    assert len(result.faces) > 0
    assert result.volume != pytest.approx(mesh.volume)


def test_vesa_pattern_is_real_geometry():
    contract = PRODUCTS["vesa-adapter"]
    mesh = REGISTRY[contract["builder"]](dict(contract["default"]))
    op = {
        "id": "vesa50",
        "type": "vesa_pattern",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0},
        "params": {"pitch_mm": 50, "diameter_mm": 4},
    }
    result = apply_operations(mesh, "vesa-adapter", [op])
    assert result.is_watertight
    assert result.volume != pytest.approx(mesh.volume)


def test_rib_is_additive_and_watertight():
    contract = PRODUCTS["vesa-adapter"]
    mesh = REGISTRY[contract["builder"]](dict(contract["default"]))
    op = {
        "id": "rib",
        "type": "rib",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0},
        "params": {"length_mm": 30, "width_mm": 4, "height_mm": 4},
    }
    result = apply_operations(mesh, "vesa-adapter", [op])
    assert result.is_watertight
    assert result.volume > mesh.volume


def test_invalid_honeycomb_size_is_rejected():
    issues = validate_operations(
        "enclosure-ip65",
        [{
            "id": "too_many",
            "type": "vent_hex",
            "version": 1,
            "enabled": True,
            "params": {"rows": 10, "cols": 10, "radius_mm": 3, "gap_mm": 2},
        }],
    )
    assert any(x["code"] == "vent_hex" for x in issues)


@pytest.mark.parametrize(
    "operation",
    [
        {
            "id": "circle",
            "type": "cutout_circle",
            "version": 1,
            "enabled": True,
            "target": {"face": "top"},
            "placement": {"x": 0, "y": 0},
            "params": {"diameter_mm": 18},
        },
        {
            "id": "counterbore",
            "type": "counterbore",
            "version": 1,
            "enabled": True,
            "target": {"face": "top"},
            "placement": {"x": 0, "y": 0},
            "params": {
                "through_diameter_mm": 5,
                "bore_diameter_mm": 10,
                "bore_depth_mm": 2,
            },
        },
    ],
    ids=["cutout_circle", "counterbore"],
)
def test_new_subtractive_operations_stay_watertight(operation):
    contract = PRODUCTS["vesa-adapter"]
    mesh = REGISTRY[contract["builder"]](dict(contract["default"]))
    result = apply_operations(mesh, "vesa-adapter", [operation])
    assert result.is_watertight
    assert result.is_winding_consistent
    assert result.volume < mesh.volume


def test_wave_ribs_create_real_watertight_surface_relief():
    contract = PRODUCTS["vesa-adapter"]
    mesh = REGISTRY[contract["builder"]](dict(contract["default"]))
    op = {
        "id": "waves",
        "type": "wave_ribs",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0, "rotation_deg": 0},
        "params": {
            "length_mm": 36,
            "rib_width_mm": 2,
            "amplitude_mm": 4,
            "count": 5,
            "spacing_mm": 5,
        },
    }
    result = apply_operations(mesh, "vesa-adapter", [op])
    assert result.is_watertight
    assert result.is_winding_consistent
    assert result.volume > mesh.volume


def test_invalid_wave_configuration_is_rejected():
    issues = validate_operations(
        "vesa-adapter",
        [{
            "id": "waves",
            "type": "wave_ribs",
            "version": 1,
            "enabled": True,
            "params": {
                "length_mm": 5,
                "rib_width_mm": 0.2,
                "amplitude_mm": 30,
                "count": 30,
                "spacing_mm": 0.5,
            },
        }],
    )
    assert any(x["code"] == "wave_ribs" for x in issues)
