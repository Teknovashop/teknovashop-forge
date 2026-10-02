from __future__ import annotations

import pytest

from model_contracts import PRODUCTS
from models import REGISTRY
from v2_operations import apply_operations, validate_operations


@pytest.mark.parametrize("slug", ["cable-tray", "vesa-adapter", "enclosure-ip65"])
def test_v2_pilots_accept_supported_operations(slug):
    issues = validate_operations(
        slug,
        [
            {
                "id": "op_hole",
                "type": "hole",
                "version": 1,
                "enabled": True,
                "target": {"face": "top"},
                "placement": {"x": 0, "y": 0},
                "params": {"diameter_mm": 4},
            }
        ],
    )
    assert issues == []


def test_v2_rejects_unknown_operation():
    issues = validate_operations(
        "vesa-adapter",
        [{"id": "x", "type": "warp", "version": 1, "enabled": True, "params": {}}],
    )
    assert any(x["code"] == "unsupported_operation" for x in issues)


def test_v2_rejects_excessive_operations():
    ops = [
        {
            "id": f"op_{i}",
            "type": "hole",
            "version": 1,
            "enabled": True,
            "params": {"diameter_mm": 4},
        }
        for i in range(25)
    ]
    issues = validate_operations("vesa-adapter", ops)
    assert any(x["code"] == "too_many_operations" for x in issues)


@pytest.mark.parametrize(
    "slug,operation",
    [
        (
            "vesa-adapter",
            {
                "id": "center_hole",
                "type": "hole",
                "version": 1,
                "enabled": True,
                "target": {"face": "top"},
                "placement": {"x": 0, "y": 0},
                "params": {"diameter_mm": 8},
            },
        ),
        (
            "vesa-adapter",
            {
                "id": "center_slot",
                "type": "slot",
                "version": 1,
                "enabled": True,
                "target": {"face": "top"},
                "placement": {"x": 0, "y": 0},
                "params": {"length_mm": 20, "width_mm": 5},
            },
        ),
        (
            "vesa-adapter",
            {
                "id": "center_cutout",
                "type": "cutout_rect",
                "version": 1,
                "enabled": True,
                "target": {"face": "top"},
                "placement": {"x": 0, "y": 0},
                "params": {"width_mm": 18, "height_mm": 10},
            },
        ),
    ],
)
def test_v2_operation_changes_geometry_and_stays_watertight(slug, operation):
    contract = PRODUCTS[slug]
    mesh = REGISTRY[contract["builder"]](dict(contract["default"]))
    result = apply_operations(mesh, slug, [operation])

    assert result.is_watertight
    assert len(result.faces) > 0
    assert abs(float(result.volume)) < abs(float(mesh.volume))
