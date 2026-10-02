from __future__ import annotations

import pytest

from model_contracts import PRODUCTS
from models import REGISTRY
from v2_operations import apply_operations, validate_operations


def _base(slug="vesa-adapter"):
    contract = PRODUCTS[slug]
    return REGISTRY[contract["builder"]](dict(contract["default"]))


def test_rectangular_pocket_is_shallow_and_watertight():
    mesh = _base()
    result = apply_operations(mesh, "vesa-adapter", [{
        "id": "pocket",
        "type": "pocket_rect",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0},
        "params": {"width_mm": 24, "height_mm": 16, "depth_mm": 1.2},
    }])
    assert result.is_watertight
    assert result.is_winding_consistent
    assert 0 < result.volume < mesh.volume


def test_boss_is_additive_and_watertight():
    mesh = _base()
    result = apply_operations(mesh, "vesa-adapter", [{
        "id": "boss",
        "type": "boss",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0},
        "params": {"diameter_mm": 14, "height_mm": 4},
    }])
    assert result.is_watertight
    assert result.is_winding_consistent
    assert result.volume > mesh.volume


def test_scallop_pattern_changes_real_geometry():
    mesh = _base()
    result = apply_operations(mesh, "vesa-adapter", [{
        "id": "scallops",
        "type": "scallop_pattern",
        "version": 1,
        "enabled": True,
        "target": {"face": "top"},
        "placement": {"x": 0, "y": 0, "rotation_deg": 0},
        "params": {"count": 3, "diameter_mm": 6, "spacing_mm": 9},
    }])
    assert result.is_watertight
    assert result.is_winding_consistent
    assert result.volume < mesh.volume


@pytest.mark.parametrize(
    "typ,params",
    [
        ("pocket_rect", {"width_mm": 1, "height_mm": 1, "depth_mm": 0.1}),
        ("boss", {"diameter_mm": 2, "height_mm": 0.2}),
        ("scallop_pattern", {"count": 30, "diameter_mm": 1, "spacing_mm": 0.2}),
    ],
)
def test_new_operations_reject_invalid_ranges(typ, params):
    issues = validate_operations("vesa-adapter", [{
        "id": typ,
        "type": typ,
        "version": 1,
        "enabled": True,
        "params": params,
    }])
    assert issues
