from __future__ import annotations
from typing import Dict, Any
import trimesh
from ._helpers import parse_holes, union

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

    cutters = []
    for x, y, d in parse_holes(params.get("holes") or []):
        r = d / 2.0
        if d <= 0:
            raise ValueError("Extra hole diameter must be greater than 0")
        if abs(x) + r > width / 2.0 or abs(y) + r > depth / 2.0:
            raise ValueError(
                f"Extra hole ({x}, {y}, Ø{d}) does not fit inside "
                f"{width} x {depth} mm tray floor"
            )

        cutter = trimesh.creation.cylinder(radius=r, height=wall * 3.0, sections=48)
        cutter.apply_translation((x, y, wall / 2.0))
        cutters.append(cutter)

    # Forge operations must see a single manifold body. Build that canonical
    # body first, then apply free-hole cutters to the resolved solid. Cutting
    # only the floor before the union can let a later brace fill the hole back in.
    mesh = union([base, left, right, *braces])
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("Cable tray union did not produce a valid solid")
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("Cable tray must be a watertight manifold before Forge operations")

    if cutters:
        for cutter in cutters:
            try:
                result = trimesh.boolean.difference([mesh, cutter], engine="manifold")
            except Exception as exc:
                raise ValueError("Cable tray free-hole boolean failed") from exc
            if not isinstance(result, trimesh.Trimesh) or not len(result.faces):
                raise ValueError("Cable tray free holes did not produce a valid solid")
            mesh = result
        if not mesh.is_watertight or not mesh.is_winding_consistent:
            raise ValueError("Cable tray free holes must preserve a watertight manifold")

    mesh.metadata = {"name": "cable_tray", "unit": "mm"}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
