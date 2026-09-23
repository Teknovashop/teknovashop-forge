from __future__ import annotations

import hashlib

import trimesh

import models.text_ops as text_ops
from models.text_ops import apply_text_ops

text_ops.DEBUG = True


def _hash(mesh: trimesh.Trimesh) -> str:
    data = mesh.export(file_type="stl")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(bytes(data)).hexdigest()


def _base_plate() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(60.0, 40.0, 5.0))


def test_emboss_text_changes_mesh_with_manifold_union():
    base = _base_plate()
    out = apply_text_ops(
        base,
        [{
            "text": "A",
            "size": 10.0,
            "depth": 1.2,
            "mode": "emboss",
            "anchor": "top",
            "pos": [0.0, 0.0, 0.0],
        }],
    )

    assert isinstance(out, trimesh.Trimesh)
    assert len(out.vertices) > 0
    assert _hash(out) != _hash(base)


def test_engrave_text_changes_mesh_with_manifold_difference():
    base = _base_plate()
    out = apply_text_ops(
        base,
        [{
            "text": "A",
            "size": 10.0,
            "depth": 1.2,
            "mode": "engrave",
            "anchor": "top",
            "pos": [0.0, 0.0, 0.0],
        }],
    )

    assert isinstance(out, trimesh.Trimesh)
    assert len(out.vertices) > 0
    assert _hash(out) != _hash(base)


def test_invalid_text_mode_fails_instead_of_silent_success():
    base = _base_plate()
    try:
        apply_text_ops(
            base,
            [{
                "text": "A",
                "size": 10.0,
                "depth": 1.2,
                "mode": "invalid",
                "anchor": "top",
                "pos": [0.0, 0.0, 0.0],
            }],
        )
    except ValueError:
        return

    raise AssertionError("Invalid text mode was silently accepted")
