
from __future__ import annotations
from typing import Dict, Any
import trimesh
from ._helpers import num, plate_with_holes, parse_holes

NAME = "camera_plate"
SLUGS = ["camera-plate"]

def make_model(p: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(num(p.get("length_mm") or p.get("length"), 120.0))
    W = float(num(p.get("width_mm") or p.get("width"), 60.0))
    T = float(num(p.get("thickness_mm") or p.get("thickness"), 3.0))
    holes = parse_holes(p.get("holes") or [])
    return plate_with_holes(L, W, T, holes)

BUILD = {"make": make_model}
