from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest
import trimesh

from model_contracts import PRODUCTS, CANONICAL_SLUGS
from models import REGISTRY


def _as_mesh(value):
    if isinstance(value, trimesh.Trimesh):
        return value
    if isinstance(value, (list, tuple)):
        meshes = [m for m in value if isinstance(m, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)
    raise AssertionError(f"Builder returned unsupported type: {type(value).__name__}")


def _build(contract, overrides=None):
    params = dict(contract["default"])
    if overrides:
        params.update(overrides)

    builder_name = contract["builder"]
    assert builder_name in REGISTRY, f"Builder '{builder_name}' is not registered"

    mesh = _as_mesh(REGISTRY[builder_name](params))
    assert len(mesh.vertices) > 0, "Mesh has no vertices"
    assert len(mesh.faces) > 0, "Mesh has no faces"

    extents = np.asarray(mesh.extents, dtype=float)
    assert np.all(np.isfinite(extents)), f"Non-finite extents: {extents}"
    assert np.all(extents > 0), f"Degenerate extents: {extents}"

    return mesh


def _stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    data = mesh.export(file_type="stl")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return bytes(data)


@pytest.mark.parametrize("slug", CANONICAL_SLUGS)
def test_default_product_generates_valid_stl(slug):
    contract = PRODUCTS[slug]
    mesh = _build(contract)

    data = _stl_bytes(mesh)
    assert len(data) > 84, "STL is too small to contain triangles"

    # STL binary starts with an 80 byte header + triangle count.
    # ASCII STL is also accepted, so the length test above is intentionally generic.
    assert math.isfinite(float(abs(mesh.volume))), "Mesh volume is not finite"

    actual = np.sort(np.asarray(mesh.extents, dtype=float))
    minimum = np.sort(np.asarray(contract["min_extents"], dtype=float))
    assert np.all(actual >= minimum * 0.90), (
        f"{slug}: geometry is unexpectedly small. "
        f"actual={actual.tolist()} minimum≈{minimum.tolist()}"
    )


@pytest.mark.parametrize("slug", CANONICAL_SLUGS)
def test_variant_parameters_change_geometry(slug):
    contract = PRODUCTS[slug]
    base = _build(contract)
    variant = _build(contract, contract["variant"])

    base_bytes = _stl_bytes(base)
    variant_bytes = _stl_bytes(variant)

    base_hash = hashlib.sha256(base_bytes).hexdigest()
    variant_hash = hashlib.sha256(variant_bytes).hexdigest()

    assert base_hash != variant_hash, (
        f"{slug}: variant parameters produced identical STL; "
        "at least one exposed parameter may not affect the geometry"
    )


def test_exactly_18_canonical_products_are_contractually_defined():
    assert len(PRODUCTS) == 18
    assert len(set(CANONICAL_SLUGS)) == 18


def test_product_contracts_have_required_metadata():
    required = {"builder", "name", "default", "variant", "min_extents"}
    for slug, contract in PRODUCTS.items():
        missing = required - set(contract)
        assert not missing, f"{slug}: missing contract keys {sorted(missing)}"
        assert contract["name"].strip(), f"{slug}: public name is empty"
        assert contract["default"], f"{slug}: default parameters are empty"
        assert contract["variant"], f"{slug}: variant parameters are empty"
