from __future__ import annotations
from typing import Dict, Any, List
import math
import trimesh

NAME = "router_mount"
SLUGS = ["router-mount", "soporte_router"]

DEFAULTS = {
    "base_w": 140.0,
    "base_h": 110.0,
    "depth": 55.0,
    "thickness": 4.0,
    "hole_d": 4.5,
    "lip_h": 16.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def _back_plate(w: float, h: float, t: float, hole_d: float) -> trimesh.Trimesh:
    plate = trimesh.creation.box(extents=(w, t, h))
    plate.apply_translation((0, 0, h / 2))

    off_x = max(12.0, w * 0.32)
    off_z = max(15.0, h * 0.30)
    cutters: List[trimesh.Trimesh] = []
    for x in (-off_x, off_x):
        for z in (h / 2 - off_z, h / 2 + off_z):
            c = trimesh.creation.cylinder(radius=hole_d / 2, height=t * 1.8, sections=64)
            c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
            c.apply_translation((x, 0, z))
            cutters.append(c)

    try:
        cutter = trimesh.util.concatenate(cutters)
        out = plate.difference(cutter)
        if isinstance(out, trimesh.Trimesh):
            return out
    except Exception:
        pass
    return plate

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    w = max(60.0, _num(params, "base_w", DEFAULTS["base_w"]))
    h = max(60.0, _num(params, "base_h", DEFAULTS["base_h"]))
    d = max(25.0, _num(params, "depth", DEFAULTS["depth"]))
    t = max(2.0, _num(params, "thickness", DEFAULTS["thickness"]))
    hd = max(2.5, _num(params, "hole_d", DEFAULTS["hole_d"]))
    lip_h = max(6.0, _num(params, "lip_h", DEFAULTS["lip_h"]))

    back = _back_plate(w, h, t, hd)

    shelf = trimesh.creation.box(extents=(w, d, t))
    shelf.apply_translation((0, d / 2 - t / 2, t / 2))

    side_l = trimesh.creation.box(extents=(t, d, lip_h))
    side_l.apply_translation((-w / 2 + t / 2, d / 2 - t / 2, lip_h / 2))
    side_r = side_l.copy()
    side_r.apply_translation((w - t, 0, 0))

    front = trimesh.creation.box(extents=(w, t, lip_h * 0.55))
    front.apply_translation((0, d - t, lip_h * 0.275))

    brace_depth = min(d * 0.55, 35.0)
    brace_h = min(h * 0.35, 38.0)
    braces = []
    for x in (-w * 0.33, w * 0.33):
        brace = trimesh.creation.box(extents=(t * 1.5, brace_depth, brace_h))
        brace.apply_translation((x, brace_depth / 2, brace_h / 2))
        braces.append(brace)

    mesh = trimesh.util.concatenate([back, shelf, side_l, side_r, front] + braces)
    mesh.metadata = {"name": "router_mount", "unit": "mm"}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
