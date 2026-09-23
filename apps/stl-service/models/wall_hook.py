from __future__ import annotations
from typing import Dict, Any

import shapely.geometry as sg
from shapely.ops import unary_union
import trimesh

from .utils_geo import circle, clean_print_solid

NAME = "wall_hook"
SLUGS = ["wall-hook", "wall-bracket-hook"]

DEFAULTS: Dict[str, float] = {
    "base_w": 40.0,
    "base_h": 60.0,
    "wall": 3.5,
    "hook_depth": 35.0,
    "hook_height": 35.0,
    "hook_t": 8.0,
    "hole_d": 4.5,
    "hole_off": 12.0,
}

def _num(p: Dict[str, Any], k: str, fb: float) -> float:
    try:
        return float(str(p.get(k, fb)).replace(",", "."))
    except Exception:
        return fb

def _plate_with_vertical_holes(
    width: float, height: float, thickness: float, hole_d: float, hole_off: float
) -> trimesh.Trimesh:
    outer = sg.box(-width / 2, -height / 2, width / 2, height / 2)
    holes = unary_union([
        circle(0.0, +height / 2 - hole_off, hole_d),
        circle(0.0, -height / 2 + hole_off, hole_d),
    ])
    shape = outer.difference(holes)
    plate = trimesh.creation.extrude_polygon(shape, thickness)
    plate = clean_print_solid(plate)
    plate.apply_translation((0.0, 0.0, -thickness / 2))
    # La placa 2D estaba en XY; la ponemos vertical XZ y el grosor pasa a Y.
    plate.apply_transform(
        trimesh.transformations.rotation_matrix(1.5707963267948966, [1, 0, 0])
    )
    return plate

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    bw = max(30.0, _num(params, "base_w", DEFAULTS["base_w"]))
    bh = max(40.0, _num(params, "base_h", DEFAULTS["base_h"]))
    plate_t = max(2.4, _num(params, "wall", DEFAULTS["wall"]))
    depth = max(15.0, _num(params, "hook_depth", DEFAULTS["hook_depth"]))
    lip_h = max(15.0, _num(params, "hook_height", DEFAULTS["hook_height"]))
    section = max(5.0, _num(params, "hook_t", DEFAULTS["hook_t"]))
    hole_d = max(3.0, _num(params, "hole_d", DEFAULTS["hole_d"]))
    hole_off = max(hole_d, min(bh * 0.4, _num(params, "hole_off", DEFAULTS["hole_off"])))

    plate = _plate_with_vertical_holes(bw, bh, plate_t, hole_d, hole_off)

    arm_z = -bh / 2 + section * 1.35
    arm = trimesh.creation.box(extents=(section, depth, section))
    arm.apply_translation((0.0, plate_t / 2 + depth / 2, arm_z))

    lip = trimesh.creation.box(extents=(section, section, lip_h))
    lip.apply_translation((
        0.0,
        plate_t / 2 + depth - section / 2,
        arm_z + lip_h / 2 - section / 2,
    ))

    brace_h = max(section * 2.0, min(lip_h * 0.55, 22.0))
    brace_d = max(section * 1.5, min(depth * 0.42, 18.0))
    brace = trimesh.creation.box(extents=(section, brace_d, brace_h))
    brace.apply_translation((
        0.0,
        plate_t / 2 + brace_d / 2,
        arm_z + brace_h / 2 - section / 2,
    ))

    mesh = trimesh.util.concatenate([plate, arm, lip, brace])
    mesh.metadata = {"name": "wall_hook", "unit": "mm"}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
