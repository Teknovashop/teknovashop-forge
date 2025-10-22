from __future__ import annotations
from typing import Dict, Any, List
import trimesh

SLUGS = ["ssd-holder"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    try: return float(str(p.get(k, d)).replace(",", "."))
    except: return d

def _box(x,y,z): return trimesh.creation.box((x,y,z))
def _union(ms: List[trimesh.Trimesh]):
    try: return trimesh.util.concatenate(ms)
    except: return ms[0]

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    drive_w = _num(params, "drive_w", 69.85)
    drive_l = _num(params, "drive_l", 100.0)
    bay_w   = _num(params, "bay_w", 101.6)
    wall    = _num(params, "wall", _num(params, "thickness_mm", 3.0))
    H       = _num(params, "height_mm", 20.0)

    base = _box(bay_w, drive_l, wall)
    base.apply_translation((0,0,wall/2))

    side = max(1.0, (bay_w - drive_w)/2)
    left  = _box(side, drive_l, H);  left.apply_translation((-drive_w/2 - side/2, 0, H/2 + wall))
    right = _box(side, drive_l, H); right.apply_translation(( drive_w/2 + side/2, 0, H/2 + wall))
    front = _box(bay_w, wall, H/2); front.apply_translation((0, -drive_l/2 + wall/2, wall + H/4))
    rear  = _box(bay_w, wall, H/2);  rear.apply_translation((0,  drive_l/2 - wall/2, wall + H/4))
    return _union([base, left, right, front, rear])

BUILD = {"make": make}
