from __future__ import annotations

import io

import numpy as np
import pytest
import trimesh

from app import _make_preview_stl_bytes
from model_contracts import CANONICAL_SLUGS, PRODUCTS
from models import REGISTRY


def _as_mesh(value):
    if isinstance(value, trimesh.Trimesh):
        return value
    if isinstance(value, (list, tuple)):
        meshes = [item for item in value if isinstance(item, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)
    raise AssertionError(f"Unsupported geometry: {type(value).__name__}")


@pytest.mark.parametrize("slug", CANONICAL_SLUGS)
def test_browser_preview_stl_is_loadable_for_every_product(slug):
    contract = PRODUCTS[slug]
    mesh = _as_mesh(REGISTRY[contract["builder"]](dict(contract["default"])))
    source = mesh.export(file_type="stl")
    if isinstance(source, str):
        source = source.encode("utf-8")

    preview_bytes, precision_mm = _make_preview_stl_bytes(bytes(source))
    assert len(preview_bytes) > 84
    assert 0.8 <= precision_mm <= 2.0

    preview = trimesh.load(
        io.BytesIO(preview_bytes),
        file_type="stl",
        force="mesh",
        process=False,
    )
    assert isinstance(preview, trimesh.Trimesh)
    assert len(preview.vertices) > 0
    assert len(preview.faces) > 0
    assert np.all(np.isfinite(preview.extents))
