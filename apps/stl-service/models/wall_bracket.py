from __future__ import annotations
from typing import Dict, Any, List
import trimesh

SLUGS = ["wall-bracket"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def _box(x,y,z): return trimesh.creation.box((x,y,z))
def _union(ms: List[trimesh.Trimesh]):
    try: return trimesh.util.concatenate(ms)
    except: return ms[0]

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = _num(params, "length_mm", 120)   # ala horizontal
    W = _num(params, "width_mm", 40)
    H = _num(params, "height_mm", 80)    # ala vertical
    T = _num(params, "thickness_mm", 4)

    base = _box(L, W, T)
    upright = _box(T, W, H)
    upright.apply_translation((L/2 - T/2, 0, H/2 + T/2))
    return _union([base, upright])

BUILD = {"make": make}
