from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "enclosure_ip65"
SLUGS = ["enclosure-ip65", "caja_ip65"]

DEFAULTS = {
    "length": 120.0,
    "width": 68.0,
    "height": 45.0,
    "wall": 3.0,
    "lid_thickness": 3.0,
    "lid_gap": 2.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def _shell(L: float, W: float, H: float, wall: float) -> trimesh.Trimesh:
    outer = trimesh.creation.box(extents=(L, W, H))
    outer.apply_translation((0, 0, H / 2))

    inner_L = max(2.0, L - 2 * wall)
    inner_W = max(2.0, W - 2 * wall)
    inner_H = max(2.0, H - wall)
    inner = trimesh.creation.box(extents=(inner_L, inner_W, inner_H + wall))
    # El cutter sobresale por arriba para dejar la caja abierta y conserva fondo.
    inner.apply_translation((0, 0, wall + (inner_H + wall) / 2))

    try:
        diff = outer.difference(inner)
        if isinstance(diff, trimesh.Trimesh):
            return diff
    except Exception:
        pass

    # Fallback sin booleanos: fondo + cuatro paredes.
    bottom = trimesh.creation.box(extents=(L, W, wall))
    bottom.apply_translation((0, 0, wall / 2))
    front = trimesh.creation.box(extents=(L, wall, H))
    front.apply_translation((0, -W / 2 + wall / 2, H / 2))
    back = front.copy(); back.apply_translation((0, W - wall, 0))
    left = trimesh.creation.box(extents=(wall, W - 2 * wall, H))
    left.apply_translation((-L / 2 + wall / 2, 0, H / 2))
    right = left.copy(); right.apply_translation((L - wall, 0, 0))
    return trimesh.util.concatenate([bottom, front, back, left, right])

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = max(50.0, _num(params, "length", DEFAULTS["length"]))
    W = max(35.0, _num(params, "width", DEFAULTS["width"]))
    H = max(20.0, _num(params, "height", DEFAULTS["height"]))
    wall = max(2.0, _num(params, "wall", DEFAULTS["wall"]))
    lid_t = max(2.0, _num(params, "lid_thickness", DEFAULTS["lid_thickness"]))
    lid_gap = max(1.0, _num(params, "lid_gap", DEFAULTS["lid_gap"]))

    base = _shell(L, W, H, wall)

    # Tapa separada ligeramente por encima para visualizar claramente las dos piezas.
    lid = trimesh.creation.box(extents=(L + wall, W + wall, lid_t))
    lid.apply_translation((0, 0, H + lid_gap + lid_t / 2))

    # Labio interior de centrado de la tapa.
    lip_outer = trimesh.creation.box(extents=(L - wall, W - wall, wall))
    lip_inner = trimesh.creation.box(extents=(L - 3 * wall, W - 3 * wall, wall * 1.4))
    try:
        lip = lip_outer.difference(lip_inner)
        if not isinstance(lip, trimesh.Trimesh):
            lip = lip_outer
    except Exception:
        lip = lip_outer
    lip.apply_translation((0, 0, H + lid_gap - wall / 2))

    mesh = trimesh.util.concatenate([base, lid, lip])
    mesh.metadata = {
        "name": "enclosure_with_lid",
        "unit": "mm",
        "note": "Parametric enclosure geometry; ingress protection rating requires physical validation.",
    }
    return mesh

BUILD = {"make": make_model, "build": make_model}
