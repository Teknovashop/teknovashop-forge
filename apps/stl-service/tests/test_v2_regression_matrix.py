from __future__ import annotations

import hashlib

import pytest

from model_contracts import PRODUCTS
from models import REGISTRY
from v2_operations import (
    ADVANCED_CAPABILITIES,
    apply_operations,
    validate_operations,
)


def _mesh(slug):
    contract = PRODUCTS[slug]
    return REGISTRY[contract["builder"]](dict(contract["default"]))


def _stl_hash(mesh):
    data = mesh.export(file_type="stl")
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(bytes(data)).hexdigest()


def test_operation_version_is_enforced_on_server():
    issues = validate_operations(
        "vesa-adapter",
        [{
            "id": "future",
            "type": "hole",
            "version": 99,
            "enabled": True,
            "params": {"diameter_mm": 5},
        }],
    )
    assert any(x["code"] == "unsupported_operation_version" for x in issues)


def test_disabled_operation_does_not_change_geometry():
    mesh = _mesh("vesa-adapter")
    result = apply_operations(
        mesh,
        "vesa-adapter",
        [{
            "id": "disabled",
            "type": "hole",
            "version": 1,
            "enabled": False,
            "params": {"diameter_mm": 8},
        }],
    )
    assert _stl_hash(result) == _stl_hash(mesh)


def test_duplicate_operation_ids_are_rejected():
    op = {
        "id": "same",
        "type": "hole",
        "version": 1,
        "enabled": True,
        "params": {"diameter_mm": 4},
    }
    issues = validate_operations("vesa-adapter", [op, dict(op)])
    assert any(x["code"] == "duplicate_id" for x in issues)


@pytest.mark.parametrize(
    "slug,operations",
    [
        (
            "vesa-adapter",
            [
                {
                    "id": "hole",
                    "type": "hole",
                    "version": 1,
                    "enabled": True,
                    "target": {"face": "top"},
                    "placement": {"x": 0, "y": 0},
                    "params": {"diameter_mm": 6},
                },
                {
                    "id": "slot",
                    "type": "slot",
                    "version": 1,
                    "enabled": True,
                    "target": {"face": "top"},
                    "placement": {"x": 0, "y": 25, "rotation_deg": 0},
                    "params": {"length_mm": 22, "width_mm": 5},
                },
                {
                    "id": "rib",
                    "type": "rib",
                    "version": 1,
                    "enabled": True,
                    "target": {"face": "top"},
                    "placement": {"x": 0, "y": -25, "rotation_deg": 0},
                    "params": {"length_mm": 30, "width_mm": 4, "height_mm": 3},
                },
            ],
        ),
        (
            "enclosure-ip65",
            [
                {
                    "id": "circle",
                    "type": "cutout_circle",
                    "version": 1,
                    "enabled": True,
                    "target": {"face": "top"},
                    "placement": {"x": -25, "y": 0},
                    "params": {"diameter_mm": 12},
                },
                {
                    "id": "vents",
                    "type": "vent_linear",
                    "version": 1,
                    "enabled": True,
                    "target": {"face": "top"},
                    "placement": {"x": 22, "y": 0, "rotation_deg": 0},
                    "params": {"count": 3, "length_mm": 20, "width_mm": 2.5, "spacing_mm": 6},
                },
            ],
        ),
    ],
)
def test_real_operation_combinations_remain_watertight(slug, operations):
    mesh = _mesh(slug)
    result = apply_operations(mesh, slug, operations)
    assert result.is_watertight
    assert result.is_winding_consistent
    assert len(result.faces) > 0
    assert _stl_hash(result) != _stl_hash(mesh)


def test_same_spec_is_reproducible():
    operations = [
        {
            "id": "hole",
            "type": "hole",
            "version": 1,
            "enabled": True,
            "target": {"face": "top"},
            "placement": {"x": 8, "y": -4},
            "params": {"diameter_mm": 5},
        },
        {
            "id": "waves",
            "type": "wave_ribs",
            "version": 1,
            "enabled": True,
            "target": {"face": "top"},
            "placement": {"x": -12, "y": 12, "rotation_deg": 0},
            "params": {
                "length_mm": 22,
                "rib_width_mm": 2,
                "amplitude_mm": 3,
                "count": 4,
                "spacing_mm": 5,
            },
        },
    ]
    a = apply_operations(_mesh("vesa-adapter"), "vesa-adapter", operations)
    b = apply_operations(_mesh("vesa-adapter"), "vesa-adapter", operations)
    assert _stl_hash(a) == _stl_hash(b)


def test_operation_outside_safe_face_fails_closed():
    with pytest.raises(ValueError, match="borde"):
        apply_operations(
            _mesh("vesa-adapter"),
            "vesa-adapter",
            [{
                "id": "edge",
                "type": "hole",
                "version": 1,
                "enabled": True,
                "target": {"face": "top"},
                "placement": {"x": 58, "y": 0},
                "params": {"diameter_mm": 10},
            }],
        )


UI_DEFAULT_OPERATIONS = {
    "hole": {"diameter_mm": 6},
    "slot": {"length_mm": 24, "width_mm": 6},
    "cutout_rect": {"width_mm": 24, "height_mm": 14},
    "cutout_circle": {"diameter_mm": 18},
    "counterbore": {
        "through_diameter_mm": 5,
        "bore_diameter_mm": 10,
        "bore_depth_mm": 2,
    },
    "pocket_rect": {"width_mm": 28, "height_mm": 18, "depth_mm": 1.2},
    "hole_pattern": {
        "diameter_mm": 4,
        "rows": 2,
        "cols": 2,
        "spacing_x_mm": 18,
        "spacing_y_mm": 18,
    },
    "vesa_pattern": {"pitch_mm": 75, "diameter_mm": 5},
    "vent_linear": {"count": 5, "length_mm": 32, "width_mm": 3, "spacing_mm": 7},
    "vent_hex": {"rows": 2, "cols": 3, "radius_mm": 3, "gap_mm": 2},
    "scallop_pattern": {"count": 3, "diameter_mm": 6, "spacing_mm": 9},
    "cable_channel": {"length_mm": 28, "width_mm": 7},
    "rib": {"length_mm": 30, "width_mm": 4, "height_mm": 4},
    "boss": {"diameter_mm": 14, "height_mm": 4},
    "wave_ribs": {
        "length_mm": 36,
        "rib_width_mm": 2,
        "amplitude_mm": 4,
        "count": 5,
        "spacing_mm": 5,
    },
}


@pytest.mark.parametrize(
    "slug,operation_type",
    [
        (slug, operation_type)
        for slug, capabilities in sorted(ADVANCED_CAPABILITIES.items())
        for operation_type in sorted(capabilities)
    ],
)
def test_every_ui_exposed_operation_generates_valid_geometry(slug, operation_type):
    """No operation may be shown in Forge unless its default UI action really works."""
    mesh = _mesh(slug)
    operation = {
        "id": f"qa-{slug}-{operation_type}",
        "type": operation_type,
        "version": 1,
        "enabled": True,
        "target": {"face": "bottom" if slug == "cable-tray" else "top"},
        "placement": {"x": 0, "y": 0, "rotation_deg": 0},
        "params": dict(UI_DEFAULT_OPERATIONS[operation_type]),
    }

    assert validate_operations(slug, [operation]) == []
    result = apply_operations(mesh, slug, [operation])

    assert result.is_watertight, f"{slug}/{operation_type} is not watertight"
    assert result.is_winding_consistent, f"{slug}/{operation_type} has inconsistent winding"
    assert len(result.faces) > 0, f"{slug}/{operation_type} produced no faces"
    assert _stl_hash(result) != _stl_hash(mesh), (
        f"{slug}/{operation_type} is exposed in the UI but does not change geometry"
    )
