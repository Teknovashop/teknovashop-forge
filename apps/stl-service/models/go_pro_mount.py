from __future__ import annotations
from typing import Dict, Any
import trimesh

SLUGS = ["go-pro-mount","gopro-mount"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    base_w = _num(params, "base_w", 30)
    base_l = _num(params, "base_l", 35)
    wall   = _num(params, "wall", 3)
    hole_d = _num(params, "hole_d", 5.2)

    body = trimesh.creation.box((base_w, base_l, wall*2))

    cyl = trimesh.creation.cylinder(radius=hole_d/2, height=base_w*1.2, sections=64)
    import numpy as np
    rot = trimesh.transformations.rotation_matrix(-np.pi/2, (0,1,0))
    cyl.apply_transform(rot)

    try:
        out = body.difference(cyl)
        if isinstance(out, trimesh.Trimesh): return out
    except Exception:
        pass
    return body

BUILD = {"make": make}
