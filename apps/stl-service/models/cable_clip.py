from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "cable_clip"
SLUGS = ["cable-clip"]

DEFAULTS = {
    "cable_d": 6.0,
    "length": 24.0,
    "gap": 1.0,
    "wall": 2.4,
    "adhesive_w": 12.0,
    "adhesive_l": 20.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def _difference(base: trimesh.Trimesh, cutter: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        result = trimesh.boolean.difference([base, cutter], engine="manifold")
        if isinstance(result, trimesh.Trimesh):
            return result
    except Exception:
        pass
    return base

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    cable_d = max(2.0, _num(params, "cable_d", DEFAULTS["cable_d"]))
    clip_len = max(8.0, _num(params, "length", DEFAULTS["length"]))
    gap = max(0.6, _num(params, "gap", DEFAULTS["gap"]))
    wall = max(1.6, _num(params, "wall", DEFAULTS["wall"]))
    adhesive_w = max(8.0, _num(params, "adhesive_w", DEFAULTS["adhesive_w"]))
    adhesive_l = max(12.0, _num(params, "adhesive_l", DEFAULTS["adhesive_l"]))

    inner_r = cable_d / 2.0 + 0.35
    outer_r = inner_r + wall

    # length controla el ancho axial real del aro.
    outer = trimesh.creation.cylinder(radius=outer_r, height=clip_len, sections=96)
    inner = trimesh.creation.cylinder(radius=inner_r, height=clip_len * 1.3, sections=96)
    ring = _difference(outer, inner)

    # gap es la abertura real del clip; puede ser menor que el cable para hacer snap-fit.
    slot = trimesh.creation.box(
        extents=(gap, outer_r * 2.4, clip_len * 1.4)
    )
    slot.apply_translation((0.0, outer_r * 0.75, 0.0))
    ring = _difference(ring, slot)

    base_t = max(1.8, wall * 0.75)
    base = trimesh.creation.box(extents=(adhesive_l, adhesive_w, base_t))
    base.apply_translation((
        0.0,
        -(outer_r + adhesive_w / 2 - wall),
        -clip_len / 2 + base_t / 2,
    ))

    neck = trimesh.creation.box(
        extents=(wall * 2.2, adhesive_w * 0.45, clip_len)
    )
    neck.apply_translation((0.0, -outer_r * 0.7, 0.0))

    mesh = trimesh.util.concatenate([ring, base, neck])
    mesh.metadata = {
        "name": "cable_clip",
        "unit": "mm",
        "cable_d": cable_d,
        "opening_mm": gap,
    }
    return mesh

BUILD = {"make": make_model, "build": make_model}
