from __future__ import annotations
from typing import Dict, Any, List
import trimesh

NAME = "camera_plate"
SLUGS = ["camera-plate"]

DEFAULTS: Dict[str, float] = {
    "width": 45.0,
    "depth": 50.0,
    "thickness": 6.0,
    "screw_d": 6.35,
    "slot_len": 18.0,
    "slot_w": 6.0,
    "chamfer": 0.8,
}

def _num(p: Dict[str, Any], k: str, fb: float) -> float:
    try:
        return float(str(p.get(k, fb)).replace(",", "."))
    except Exception:
        return fb

def _slot_cutters(slot_len: float, slot_w: float, height: float) -> List[trimesh.Trimesh]:
    r = slot_w * 0.5
    core_len = max(0.1, slot_len - slot_w)
    core = trimesh.creation.box(extents=(slot_w, core_len, height))
    cap = trimesh.creation.cylinder(radius=r, height=height, sections=64)
    cap1 = cap.copy(); cap1.apply_translation((0.0, +core_len * 0.5, 0.0))
    cap2 = cap.copy(); cap2.apply_translation((0.0, -core_len * 0.5, 0.0))
    return [core, cap1, cap2]

def _difference(base: trimesh.Trimesh, cutters: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    try:
        result = trimesh.boolean.difference([base, *cutters], engine="manifold")
        if isinstance(result, trimesh.Trimesh):
            return result
    except Exception:
        pass
    return base

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    W = max(30.0, _num(params, "width", DEFAULTS["width"]))
    D = max(35.0, _num(params, "depth", DEFAULTS["depth"]))
    T = max(3.0, _num(params, "thickness", DEFAULTS["thickness"]))
    d0 = max(5.5, _num(params, "screw_d", DEFAULTS["screw_d"]))
    slot_len = max(d0 + 2.0, _num(params, "slot_len", DEFAULTS["slot_len"]))
    slot_w = max(d0, _num(params, "slot_w", DEFAULTS["slot_w"]))

    base = trimesh.creation.box(extents=(W, D, T))

    hole = trimesh.creation.cylinder(radius=d0 * 0.5, height=T * 1.8, sections=96)
    cutters: List[trimesh.Trimesh] = [hole]

    slot_parts = _slot_cutters(slot_len, slot_w, T * 1.8)
    for part in slot_parts:
        part.apply_translation((W * 0.18, 0.0, 0.0))
        cutters.append(part)

    plate = _difference(base, cutters)
    plate.metadata = {"name": "camera_plate", "unit": "mm"}
    return plate

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
