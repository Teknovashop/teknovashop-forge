from __future__ import annotations

from typing import Dict, Any
import trimesh

NAME = "headset_stand"
SLUGS = ["headset-stand", "soporte-auriculares"]

DEFAULTS = {
    "base_w": 120.0,
    "base_d": 120.0,
    "stem_h": 260.0,
    "stem_w": 30.0,
    "hook_r": 40.0,
    "wall": 4.0,
}

def _num(p: Dict[str, Any], key: str, default: float, *aliases: str) -> float:
    for k in (key, *aliases):
        if k in p and p[k] is not None:
            try:
                return float(str(p[k]).replace(",", "."))
            except Exception:
                pass
    return float(default)

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    base_w = max(80.0, _num(params, "base_w", DEFAULTS["base_w"], "length_mm"))
    base_d = max(80.0, _num(params, "base_d", DEFAULTS["base_d"], "width_mm"))
    stem_h = max(180.0, _num(params, "stem_h", DEFAULTS["stem_h"], "height_mm"))
    stem_w = max(18.0, _num(params, "stem_w", DEFAULTS["stem_w"]))
    support_half = max(20.0, _num(params, "hook_r", DEFAULTS["hook_r"]))
    wall = max(3.0, _num(params, "wall", DEFAULTS["wall"], "thickness_mm"))

    base = trimesh.creation.box(extents=(base_w, base_d, wall))
    base.apply_translation((0.0, 0.0, wall / 2))

    # Mástil ligeramente retrasado para que el centro de gravedad quede sobre la base.
    stem = trimesh.creation.box(extents=(stem_w, wall * 2.0, stem_h))
    stem.apply_translation((0.0, base_d * 0.16, wall + stem_h / 2))

    support_w = support_half * 2.0
    saddle = trimesh.creation.box(extents=(support_w, stem_w, wall * 2.0))
    saddle.apply_translation((0.0, base_d * 0.16, wall + stem_h + wall))

    # Labios laterales para que la diadema no deslice.
    lip_h = max(10.0, wall * 3.0)
    lips = []
    for x in (-support_w / 2 + wall / 2, support_w / 2 - wall / 2):
        lip = trimesh.creation.box(extents=(wall, stem_w, lip_h))
        lip.apply_translation((x, base_d * 0.16, wall + stem_h + lip_h / 2))
        lips.append(lip)

    # Refuerzo entre mástil y apoyo superior.
    gusset = trimesh.creation.box(extents=(stem_w * 1.6, stem_w, wall * 3.0))
    gusset.apply_translation((0.0, base_d * 0.16, wall + stem_h - wall))

    mesh = trimesh.util.concatenate([base, stem, saddle, *lips, gusset])
    mesh.metadata = {"name": "headset_stand", "unit": "mm"}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
