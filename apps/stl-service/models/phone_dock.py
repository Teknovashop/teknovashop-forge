from __future__ import annotations
from typing import Dict, Any
import trimesh

SLUGS = ["phone-dock"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    bw = _num(params, "base_w", _num(params, "length_mm", 90))
    bd = _num(params, "base_d", _num(params, "width_mm", 110))
    wall = _num(params, "wall", _num(params, "thickness_mm", 4))
    height = _num(params, "height_mm", 80)
    slot_w = _num(params, "slot_w", 12)
    slot_d = _num(params, "slot_d", 12)

    base = trimesh.creation.box((bw, bd, wall))
    back = trimesh.creation.box((bw, wall, height))
    back.apply_translation((0, bd/2 - wall/2, height/2 + wall/2))

    dock = trimesh.util.concatenate([base, back])

    slot = trimesh.creation.box((slot_w, slot_d, wall*2.0))
    slot.apply_translation((0, bd/2 - slot_d/2 - wall/2, wall))
    try:
        out = dock.difference(slot)
        if isinstance(out, trimesh.Trimesh): return out
    except Exception:
        pass
    return dock

BUILD = {"make": make}
