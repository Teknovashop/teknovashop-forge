# apps/stl-service/models/camera_plate.py
from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "camera_plate"

def _bool_diff(base: trimesh.Trimesh, cutter: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        engine = "scad" if trimesh.interfaces.scad.exists else None
        out = base.difference(cutter, engine=engine)
        if isinstance(out, list):
            return trimesh.util.concatenate(out)
        return out or base
    except Exception:
        try:
            out = trimesh.boolean.difference([base, cutter], engine="scad" if trimesh.interfaces.scad.exists else None)
            if isinstance(out, list):
                return trimesh.util.concatenate(out)
            return out or base
        except Exception:
            return base

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    # UI: width, depth, thickness, screw_d, slot_len, chamfer
    w = float(params.get("width", 45))
    d = float(params.get("depth", 50))
    t = float(params.get("thickness", 6))
    screw_d = float(params.get("screw_d", 6.35))
    slot_len = float(params.get("slot_len", 18))
    # chamfer no se aplica en este builder mínimo

    plate = trimesh.creation.box(extents=(w, d, t))
    plate.apply_translation((0, 0, t/2))

    # agujero central 1/4"
    hole = trimesh.creation.cylinder(radius=screw_d/2.0, height=t*1.4, sections=64)
    hole.apply_translation((0, 0, t/2))
    plate = _bool_diff(plate, hole)

    # ranura longitudinal (ancho ~ diámetro del tornillo)
    slot = trimesh.creation.box(extents=(screw_d, slot_len, t*1.4))
    slot.apply_translation((0, d/2 - slot_len/2 - screw_d, t/2))
    plate = _bool_diff(plate, slot)

    return plate

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
