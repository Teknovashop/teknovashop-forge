from __future__ import annotations

import hashlib

import pytest

from model_contracts import PRODUCTS
from models import REGISTRY
from v2_operations import apply_operations, validate_operations


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
