
from __future__ import annotations
from typing import Dict, Any
import trimesh
from ._helpers import num, box

NAME = "phone_dock"
SLUGS = ["phone-dock"]

def make_model(p: Dict[str, Any]) -> trimesh.Trimesh:
    W = float(num(p.get("base_w") or p.get("length_mm"), 90.0))
    D = float(num(p.get("base_d") or p.get("width_mm"), 110.0))
    T = float(num(p.get("wall") or p.get("thickness_mm"), 4.0))

    base = box((W, D, T))
    back = box((W, T, D * 0.7))
    back.apply_translation((0, -D / 2 + T / 2, D * 0.35))
    lip = box((W, T, T * 1.5))
    lip.apply_translation((0, D / 2 - T / 2, T * 0.75))
    return trimesh.util.concatenate([base, back, lip])

BUILD = {"make": make_model}
