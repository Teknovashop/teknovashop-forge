from __future__ import annotations
from typing import Dict, Any, List, Tuple
import trimesh

NAME = "wall_hook"
SLUGS = ["wall-hook", "wall-bracket-hook"]

DEFAULTS: Dict[str, float] = {
    "base_w": 40.0,
    "base_h": 60.0,
    "wall": 3.5,
    "hook_depth": 35.0,
    "hook_height": 35.0,
    "hook_t": 8.0,
    "hole_d": 4.5,
    "hole_off": 12.0,
}

def _num(p: Dict[str, Any], k: str, fb: float) -> float:
    try:
        return float(str(p.get(k, fb)).replace(",", "."))
    except Exception:
        return fb

def _holes_grid(h: float, off: float, d: float) -> List[Tuple[float, float, float]]:
    return [(0.0, h * 0.5 - off, d), (0.0, -h * 0.5 + off, d)]

def _difference(base: trimesh.Trimesh, cutters: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    if not cutters:
        return base
    try:
        result = trimesh.boolean.difference([base, *cutters], engine="manifold")
        if isinstance(result, trimesh.Trimesh):
            return result
    except Exception:
        pass
    return base

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    bw = max(30.0, _num(params, "base_w", DEFAULTS["base_w"]))
    bh = max(40.0, _num(params, "base_h", DEFAULTS["base_h"]))
    t = max(2.4, _num(params, "wall", DEFAULTS["wall"]))
    gd = max(15.0, _num(params, "hook_depth", DEFAULTS["hook_depth"]))
    gh = max(15.0, _num(params, "hook_height", DEFAULTS["hook_height"]))
    gt = max(5.0, _num(params, "hook_t", DEFAULTS["hook_t"]))
    hd = max(3.0, _num(params, "hole_d", DEFAULTS["hole_d"]))
    off = max(hd, min(bh * 0.4, _num(params, "hole_off", DEFAULTS["hole_off"])))

    plate = trimesh.creation.box(extents=(bw, bh, t))
    cutters: List[trimesh.Trimesh] = []
    for x, y, d in _holes_grid(bh, off, hd):
        c = trimesh.creation.cylinder(radius=d * 0.5, height=t * 1.8, sections=72)
        c.apply_translation((x, y, 0.0))
        cutters.append(c)
    plate = _difference(plate, cutters)

    arm = trimesh.creation.box(extents=(gd, gt, t))
    arm.apply_translation((bw / 2 + gd / 2, -bh / 2 + gt / 2 + 2.0, 0.0))

    lip = trimesh.creation.box(extents=(gt, gh, t))
    lip.apply_translation((bw / 2 + gd - gt / 2, -bh / 2 + gh / 2 + 2.0, 0.0))

    mesh = trimesh.util.concatenate([plate, arm, lip])
    mesh.metadata = {"name": "wall_hook", "unit": "mm"}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
