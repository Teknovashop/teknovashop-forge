from __future__ import annotations

import hashlib

import pytest

from model_contracts import PRODUCTS
from models import REGISTRY
from v2_operations import PRODUCT_CAPABILITIES, apply_operations, validate_operations


def _mesh(slug: str):
    contract = PRODUCTS[slug]
    return REGISTRY[contract["builder"]](dict(contract["default"]))


def _hash(mesh):
    data = mesh.export(file_type="stl")
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(bytes(data)).hexdigest()


def test_every_canonical_product_is_v2_addressable():
    assert set(PRODUCT_CAPABILITIES) == set(PRODUCTS)
    for slug in PRODUCTS:
        assert validate_operations(slug, []) == []


def test_products_without_advanced_geometry_fail_closed():
    for slug, capabilities in PRODUCT_CAPABILITIES.items():
        if capabilities:
            continue
        issues = validate_operations(
            slug,
            [{
                "id": "unsupported",
                "type": "hole",
                "version": 1,
                "enabled": True,
                "params": {"diameter_mm": 4},
            }],
        )
        assert any(issue["code"] == "unsupported_operation" for issue in issues)


@pytest.mark.parametrize(
    "slug,placement",
    [
        ("qr-plate", {"x": 18, "y": 0}),
        ("camera-plate", {"x": 12, "y": 8}),
        ("universal-mount-plate", {"x": 10, "y": 8}),
        ("vesa-offset-adapter", {"x": 10, "y": 8}),
        ("perforated-mount-plate", {"x": 10, "y": 8}),
        ("circular-pattern-adapter", {"x": 8, "y": 8}),
        ("drill-template", {"x": 8, "y": 8}),
        ("multipattern-transition-plate", {"x": 10, "y": 8}),
        ("inset-label", {"x": 10, "y": 0}),
        ("parametric-spacer", {"x": 8, "y": 0}),
    ],
)
def test_extended_planar_products_accept_real_v2_holes(slug, placement):
    base = _mesh(slug)
    result = apply_operations(
        base,
        slug,
        [{
            "id": "regression-hole",
            "type": "hole",
            "version": 1,
            "enabled": True,
            "target": {"face": "top"},
            "placement": placement,
            "params": {"diameter_mm": 4},
        }],
    )
    assert result.is_watertight
    assert result.is_winding_consistent
    assert len(result.faces) > 0
    assert _hash(result) != _hash(base)
