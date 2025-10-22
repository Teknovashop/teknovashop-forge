from __future__ import annotations
from typing import Dict, Any
import trimesh

SLUGS = ["raspi-case"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    w = _num(params, "board_w", 85.0)
    l = _num(params, "board_l", 56.0)
    h = _num(params, "board_h", 17.0)
    wall = _num(params, "wall", 2.2)

    outer = trimesh.creation.box((w + 2*wall, l + 2*wall, h + wall))
    inner = trimesh.creation.box((w, l, h))
    inner.apply_translation((0,0,wall/2))
    try:
        out = outer.difference(inner)
        if isinstance(out, trimesh.Trimesh): return out
    except Exception:
        pass
    return outer

BUILD = {"make": make}
