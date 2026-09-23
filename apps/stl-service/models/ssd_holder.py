from __future__ import annotations
from typing import Dict, Any, List
import trimesh

from .utils_geo import plate_with_holes

NAME = "ssd_holder"
SLUGS = ["ssd-holder"]

DEFAULTS = {
    "drive_w": 69.85,
    "drive_l": 100.0,
    "bay_w": 101.6,
    "wall": 3.0,
    "hole_d": 3.2,
    "tolerance": 0.5,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    drive_w = max(60.0, _num(params, "drive_w", DEFAULTS["drive_w"]))
    drive_l = max(80.0, _num(params, "drive_l", DEFAULTS["drive_l"]))
    bay_w = max(85.0, _num(params, "bay_w", DEFAULTS["bay_w"]))
    wall = max(2.0, _num(params, "wall", DEFAULTS["wall"]))
    hole_d = max(2.5, _num(params, "hole_d", DEFAULTS["hole_d"]))
    tolerance = max(0.1, _num(params, "tolerance", DEFAULTS["tolerance"]))

    inner_w = drive_w + 2.0 * tolerance
    outer_l = drive_l + 2.0 * tolerance
    bay_w = max(bay_w, inner_w + 2.0 * wall)

    # Cuatro taladros de montaje configurables en la base.
    hole_x = min(inner_w * 0.42, bay_w / 2 - wall * 2.0)
    hole_y = min(drive_l * 0.38, outer_l / 2 - wall * 2.0)
    holes = [
        (-hole_x, -hole_y, hole_d),
        (+hole_x, -hole_y, hole_d),
        (-hole_x, +hole_y, hole_d),
        (+hole_x, +hole_y, hole_d),
    ]
    base = plate_with_holes(bay_w, outer_l, wall, holes)

    rail_h = max(14.0, wall * 5.0)
    rail_t = max(wall, (bay_w - inner_w) / 2.0)

    left = trimesh.creation.box(extents=(rail_t, outer_l, rail_h))
    left.apply_translation((-inner_w / 2 - rail_t / 2, 0.0, wall + rail_h / 2))

    right = trimesh.creation.box(extents=(rail_t, outer_l, rail_h))
    right.apply_translation((+inner_w / 2 + rail_t / 2, 0.0, wall + rail_h / 2))

    front = trimesh.creation.box(extents=(bay_w, wall, rail_h * 0.55))
    front.apply_translation((0.0, -outer_l / 2 + wall / 2, wall + rail_h * 0.275))

    rear = trimesh.creation.box(extents=(bay_w, wall, rail_h * 0.55))
    rear.apply_translation((0.0, +outer_l / 2 - wall / 2, wall + rail_h * 0.275))

    mesh = trimesh.util.concatenate([base, left, right, front, rear])
    mesh.metadata = {
        "name": "ssd_holder",
        "unit": "mm",
        "drive_clearance_mm": tolerance,
    }
    return mesh

BUILD = {"make": make, "build": make}
