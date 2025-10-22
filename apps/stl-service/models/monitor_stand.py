
from __future__ import annotations
from typing import Dict, Any
import trimesh
from ._helpers import num, box, difference

NAME = "monitor_stand"
SLUGS = ["monitor-stand"]

def make_model(p: Dict[str, Any]) -> trimesh.Trimesh:
    W = float(num(p.get("width") or p.get("length_mm"), 400.0))
    D = float(num(p.get("depth") or p.get("width_mm"), 200.0))
    H = float(num(p.get("height") or p.get("height_mm"), 70.0))
    T = float(num(p.get("wall") or p.get("thickness_mm"), 4.0))

    outer = box((W, D, H))
    inner = box((max(W - 2 * T, 1), max(D - 2 * T, 1), max(H - 2 * T, 1)))
    return difference(outer, inner)

BUILD = {"make": make_model}
