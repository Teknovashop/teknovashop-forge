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

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    cable_d = max(2.0, _num(params, "cable_d", DEFAULTS["cable_d"]))
    clip_len = max(14.0, _num(params, "length", DEFAULTS["length"]))
    gap = max(0.8, _num(params, "gap", DEFAULTS["gap"]))
    wall = max(1.6, _num(params, "wall", DEFAULTS["wall"]))
    adhesive_w = max(8.0, _num(params, "adhesive_w", DEFAULTS["adhesive_w"]))
    adhesive_l = max(12.0, _num(params, "adhesive_l", DEFAULTS["adhesive_l"]))

    inner_r = cable_d / 2.0 + 0.35
    outer_r = inner_r + wall
    width_z = min(max(adhesive_w * 0.7, 7.0), 16.0)

    outer = trimesh.creation.cylinder(radius=outer_r, height=width_z, sections=96)
    inner = trimesh.creation.cylinder(radius=inner_r, height=width_z * 1.4, sections=96)
    try:
        ring = outer.difference(inner)
        if not isinstance(ring, trimesh.Trimesh):
            ring = outer
    except Exception:
        ring = outer

    # Apertura en la parte superior para introducir el cable a presión.
    slot_w = max(gap, cable_d * 0.45)
    slot = trimesh.creation.box(extents=(slot_w, outer_r * 1.7, width_z * 1.5))
    slot.apply_translation((0, outer_r * 0.75, 0))
    try:
        opened = ring.difference(slot)
        if isinstance(opened, trimesh.Trimesh):
            ring = opened
    except Exception:
        pass

    # Base plana para cinta adhesiva / tornillo.
    base_t = max(1.8, wall * 0.75)
    base = trimesh.creation.box(extents=(adhesive_l, adhesive_w, base_t))
    base.apply_translation((0, -(outer_r + adhesive_w / 2 - wall), -width_z / 2 + base_t / 2))

    # Cuello entre aro y base.
    neck = trimesh.creation.box(extents=(wall * 2.2, adhesive_w * 0.45, width_z))
    neck.apply_translation((0, -outer_r * 0.7, 0))

    mesh = trimesh.util.concatenate([ring, base, neck])
    mesh.metadata = {"name": "cable_clip", "unit": "mm", "cable_d": cable_d}
    return mesh

BUILD = {"make": make_model, "build": make_model}
