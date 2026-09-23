from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "hub_holder"
SLUGS = ["hub-holder", "soporte-hub"]

DEFAULTS = {
    "hub_w": 100.0,
    "hub_h": 28.0,
    "hub_d": 30.0,
    "tolerance": 0.5,
    "wall": 3.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def _hollow_holder(
    inner_w: float,
    inner_h: float,
    inner_d: float,
    wall: float,
) -> trimesh.Trimesh:
    outer_w = inner_w + 2 * wall
    outer_h = inner_h + wall
    outer_d = inner_d + 2 * wall

    outer = trimesh.creation.box(extents=(outer_w, outer_d, outer_h))
    outer.apply_translation((0.0, 0.0, outer_h / 2))

    inner = trimesh.creation.box(
        extents=(inner_w, inner_d, inner_h + wall)
    )
    # Sobresale por arriba: deja fondo + paredes y apertura superior.
    inner.apply_translation((0.0, 0.0, wall + (inner_h + wall) / 2))

    try:
        result = trimesh.boolean.difference(
            [outer, inner],
            engine="manifold",
        )
        if isinstance(result, trimesh.Trimesh):
            return result
    except Exception:
        pass

    # Fallback que conserva la semántica: fondo + cuatro paredes, nunca bloque sólido.
    bottom = trimesh.creation.box(extents=(outer_w, outer_d, wall))
    bottom.apply_translation((0.0, 0.0, wall / 2))

    left = trimesh.creation.box(extents=(wall, outer_d, outer_h))
    left.apply_translation((-outer_w / 2 + wall / 2, 0.0, outer_h / 2))
    right = left.copy()
    right.apply_translation((outer_w - wall, 0.0, 0.0))

    front = trimesh.creation.box(extents=(inner_w, wall, outer_h))
    front.apply_translation((0.0, -outer_d / 2 + wall / 2, outer_h / 2))
    rear = front.copy()
    rear.apply_translation((0.0, outer_d - wall, 0.0))

    return trimesh.util.concatenate([bottom, left, right, front, rear])

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    hub_w = max(40.0, _num(params, "hub_w", DEFAULTS["hub_w"]))
    hub_h = max(10.0, _num(params, "hub_h", DEFAULTS["hub_h"]))
    hub_d = max(12.0, _num(params, "hub_d", DEFAULTS["hub_d"]))
    tolerance = max(0.0, _num(params, "tolerance", DEFAULTS["tolerance"]))
    wall = max(1.8, _num(params, "wall", DEFAULTS["wall"]))

    inner_w = hub_w + 2 * tolerance
    inner_h = hub_h + tolerance
    inner_d = hub_d + 2 * tolerance

    mesh = _hollow_holder(inner_w, inner_h, inner_d, wall)
    mesh.metadata = {
        "name": "hub_holder",
        "unit": "mm",
        "clearance_mm": tolerance,
    }
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
