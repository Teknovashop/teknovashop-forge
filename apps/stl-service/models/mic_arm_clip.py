from __future__ import annotations
from typing import Dict, Any
import trimesh

SLUGS = ["mic-arm-clip"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    arm_d = _num(params, "arm_d", 20.0)
    clip_t = _num(params, "clip_t", 3.0)
    width = _num(params, "width", 14.0)
    opening = _num(params, "opening", 0.6)

    outer = trimesh.creation.cylinder(radius=(arm_d/2+clip_t), height=width, sections=96)
    inner = trimesh.creation.cylinder(radius=(arm_d/2), height=width*1.2, sections=96)
    try:
        ring = outer.difference(inner)
        slot = trimesh.creation.box((opening, (arm_d+clip_t*2), width*1.3))
        slot.apply_translation((arm_d/2,0,0))
        out = ring.difference(slot)
        if isinstance(out, trimesh.Trimesh): return out
    except Exception:
        pass
    return outer

BUILD = {"make": make}
