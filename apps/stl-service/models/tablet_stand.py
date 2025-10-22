
from __future__ import annotations
from typing import Dict, Any
import trimesh
from ._helpers import num, box

NAME = "tablet_stand"
SLUGS = ["tablet-stand"]

def make_model(p: Dict[str, Any]) -> trimesh.Trimesh:
    W = float(num(p.get("width") or p.get("length_mm"), 160.0))
    D = float(num(p.get("depth") or p.get("width_mm"), 140.0))
    wall = float(num(p.get("wall") or p.get("thickness_mm"), 4.0))
    lip = float(num(p.get("lip_h"), 10.0))

    base = box((W, D, wall))
    back = box((W, wall, D * 0.8))
    back.apply_translation((0, -D / 2 + wall / 2, D * 0.4))
    lipm = box((W, wall, lip))
    lipm.apply_translation((0, D / 2 - wall / 2, wall / 2 + lip / 2))
    return trimesh.util.concatenate([base, back, lipm])

BUILD = {"make": make_model}
