# apps/stl-service/models/go_pro_mount.py
from __future__ import annotations
from typing import Dict, Any, List
import math
import trimesh
from trimesh.transformations import rotation_matrix

NAME = "go_pro_mount"

def _bool_diff(base: trimesh.Trimesh, cutter: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        engine = "scad" if trimesh.interfaces.scad.exists else None
        out = base.difference(cutter, engine=engine)
        if isinstance(out, list):
            return trimesh.util.concatenate(out)
        return out or base
    except Exception:
        try:
            out = trimesh.boolean.difference([base, cutter], engine="scad" if trimesh.interfaces.scad.exists else None)
            if isinstance(out, list):
                return trimesh.util.concatenate(out)
            return out or base
        except Exception:
            return base

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    # UI: fork_pitch, ear_t, hole_d, base_w, base_l, wall
    pitch = float(params.get("fork_pitch", 17.5))  # distancia entre centros de orejas
    ear_t = float(params.get("ear_t", 3.2))
    hole_d = float(params.get("hole_d", 5.2))
    bw = float(params.get("base_w", 30))
    bl = float(params.get("base_l", 35))
    t = float(params.get("wall", 3))

    base = trimesh.creation.box(extents=(bw, bl, t*2))
    base.apply_translation((0, 0, t))

    ear_h = t*2.5
    ear_d = t*2 + bl*0.3
    ear = trimesh.creation.box(extents=(ear_t, ear_d, ear_h))

    left = ear.copy()
    left.apply_translation((-pitch/2, 0, t + ear_h/2))
    right = ear.copy()
    right.apply_translation(( pitch/2, 0, t + ear_h/2))

    mount = trimesh.util.concatenate([base, left, right])

    # taladro pasante en orejas (eje Y)
    cyl = trimesh.creation.cylinder(radius=hole_d/2.0, height=ear_d*1.2, sections=48)
    # cil eje Z -> rotar 90º sobre X para que el eje quede en Y
    R = rotation_matrix(math.pi/2, (1, 0, 0))
    cyl.apply_transform(R)
    cyl.apply_translation((0, 0, t + ear_h/2))
    mount = _bool_diff(mount, cyl)

    return mount

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
