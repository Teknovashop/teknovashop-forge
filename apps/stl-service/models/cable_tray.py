from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "cable_tray"
SLUGS = ["cable-tray", "bandeja-cables"]

DEFAULTS = {
    "width": 220.0,
    "depth": 80.0,
    "height": 50.0,
    "wall": 4.0,
}

def _num(p: Dict[str, Any], key: str, default: float, *aliases: str) -> float:
    for k in (key, *aliases):
        if k in p and p[k] is not None:
            try:
                return float(str(p[k]).replace(",", "."))
            except Exception:
                pass
    return float(default)

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    width = max(100.0, _num(params, "width", DEFAULTS["width"], "length"))
    depth = max(40.0, _num(params, "depth", DEFAULTS["depth"]))
    height = max(25.0, _num(params, "height", DEFAULTS["height"]))
    wall = max(2.0, _num(params, "wall", DEFAULTS["wall"], "thickness"))

    # Bandeja en U: X ancho/largo, Y fondo, Z altura.
    base = trimesh.creation.box(extents=(width, depth, wall))
    base.apply_translation((0.0, 0.0, wall / 2))

    left = trimesh.creation.box(extents=(width, wall, height))
    left.apply_translation((0.0, -depth / 2 + wall / 2, height / 2))

    right = trimesh.creation.box(extents=(width, wall, height))
    right.apply_translation((0.0, depth / 2 - wall / 2, height / 2))

    # Dos refuerzos inferiores cortos que dan rigidez sin cerrar la bandeja.
    brace_w = max(wall * 2.0, min(18.0, depth * 0.18))
    braces = []
    for x in (-width * 0.30, width * 0.30):
        brace = trimesh.creation.box(extents=(wall * 2.0, depth, wall * 1.5))
        brace.apply_translation((x, 0.0, wall * 0.75))
        braces.append(brace)

    mesh = trimesh.util.concatenate([base, left, right, *braces])
    mesh.metadata = {"name": "cable_tray", "unit": "mm"}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
