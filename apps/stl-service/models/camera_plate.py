from __future__ import annotations
from typing import Dict, Any

import shapely.geometry as sg
from shapely.ops import unary_union
import trimesh

from .utils_geo import circle, slot, clean_print_solid

NAME = "camera_plate"
SLUGS = ["camera-plate"]

DEFAULTS: Dict[str, float] = {
    "width": 45.0,
    "depth": 50.0,
    "thickness": 6.0,
    "screw_d": 6.35,
    "slot_len": 18.0,
    "slot_w": 6.0,
    "chamfer": 0.8,
}

def _num(p: Dict[str, Any], k: str, fb: float) -> float:
    try:
        return float(str(p.get(k, fb)).replace(",", "."))
    except Exception:
        return fb

def _chamfered_rectangle(width: float, depth: float, chamfer: float) -> sg.Polygon:
    x = width / 2.0
    y = depth / 2.0
    c = max(0.0, min(chamfer, min(width, depth) * 0.22))
    if c <= 0.001:
        return sg.box(-x, -y, x, y)
    return sg.Polygon([
        (-x + c, -y), (x - c, -y), (x, -y + c), (x, y - c),
        (x - c, y), (-x + c, y), (-x, y - c), (-x, -y + c),
    ])

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    width = max(30.0, _num(params, "width", DEFAULTS["width"]))
    depth = max(35.0, _num(params, "depth", DEFAULTS["depth"]))
    thickness = max(3.0, _num(params, "thickness", DEFAULTS["thickness"]))
    screw_d = max(5.5, _num(params, "screw_d", DEFAULTS["screw_d"]))
    slot_len = max(screw_d + 2.0, _num(params, "slot_len", DEFAULTS["slot_len"]))
    slot_w = max(screw_d, _num(params, "slot_w", DEFAULTS["slot_w"]))
    chamfer = max(0.0, _num(params, "chamfer", DEFAULTS["chamfer"]))

    outline = _chamfered_rectangle(width, depth, chamfer)
    centre_hole = circle(0.0, 0.0, screw_d)
    adjustment_slot = slot(width * 0.18, 0.0, slot_len, slot_w, angle_deg=90.0)

    shape = outline.difference(unary_union([centre_hole, adjustment_slot]))
    mesh = trimesh.creation.extrude_polygon(shape, thickness)
    mesh = clean_print_solid(mesh)
    mesh.apply_translation((0.0, 0.0, -thickness / 2.0))
    mesh.metadata = {
        "name": "camera_plate",
        "unit": "mm",
        "chamfer_mm": chamfer,
    }
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
