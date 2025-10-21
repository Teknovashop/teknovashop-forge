# apps/stl-service/models/phone_dock.py
from __future__ import annotations
from typing import Dict, Any
import math
import trimesh
from trimesh.transformations import rotation_matrix

NAME = "phone_dock"

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
    # UI: base_w, base_d, angle_deg, slot_w, slot_d, usb_clear_h, wall
    bw = float(params.get("base_w", 90))
    bd = float(params.get("base_d", 110))
    ang = float(params.get("angle_deg", 62))
    slot_w = float(params.get("slot_w", 12))
    slot_d = float(params.get("slot_d", 12))
    usb_h = float(params.get("usb_clear_h", 6))
    t = float(params.get("wall", 4))

    base = trimesh.creation.box(extents=(bw, bd, t))
    base.apply_translation((0, 0, t/2))

    back_h = max(bd * 0.85, 90.0)
    back = trimesh.creation.box(extents=(bw, t, back_h))
    back.apply_translation((0, bd/2 - t/2, back_h/2))
    R = rotation_matrix(math.radians(ang), (1, 0, 0), point=(0, bd/2 - t/2, t))
    back.apply_transform(R)

    dock = trimesh.util.concatenate([base, back])

    # Ranura para el teléfono
    cutter = trimesh.creation.box(extents=(slot_w, slot_d, usb_h))
    cutter.apply_translation((0, 0, t + usb_h/2))
    dock = _bool_diff(dock, cutter)
    return dock

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
