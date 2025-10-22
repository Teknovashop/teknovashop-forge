from __future__ import annotations
from typing import Dict, Any
import trimesh

SLUGS = ["camera-plate"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = _num(params, "length_mm", 50)
    W = _num(params, "width_mm", 45)
    T = _num(params, "thickness_mm", 6)
    screw_d = _num(params, "screw_d", 6.35)  # 1/4"
    slot_len = _num(params, "slot_len", 18)
    slot_w = _num(params, "slot_w", 6)

    plate = trimesh.creation.box((L, W, T))

    hole = trimesh.creation.cylinder(radius=screw_d/2, height=T*1.5, sections=64)
    slot = trimesh.creation.box((slot_len, slot_w, T*1.6))

    try:
        out = plate.difference([hole, slot])
        if isinstance(out, trimesh.Trimesh): return out
    except Exception:
        pass
    return plate

BUILD = {"make": make}
