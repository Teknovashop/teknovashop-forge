# apps/stl-service/models/tablet_stand.py
from __future__ import annotations
import math
from typing import Dict, Any, List
import trimesh
from trimesh.transformations import rotation_matrix

NAME = "tablet_stand"

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
    # UI: width, depth, angle_deg, lip_h, wall
    w = float(params.get("width", 160))
    d = float(params.get("depth", 140))
    ang = float(params.get("angle_deg", 65))
    lip_h = float(params.get("lip_h", 10))
    t = float(params.get("wall", 4))

    # Base
    base = trimesh.creation.box(extents=(w, d, t))
    base.apply_translation((0, 0, t/2))

    # Respaldo (lo hacemos de altura proporcional a 'depth')
    back_h = max(d * 0.8, 80.0)
    back = trimesh.creation.box(extents=(w, t, back_h))
    # rotación sobre eje X para simular el ángulo solicitado
    R = rotation_matrix(math.radians(ang), (1, 0, 0), point=(0, d/2 - t/2, t))
    back.apply_translation((0, d/2 - t/2, back_h/2))
    back.apply_transform(R)

    # Labio frontal
    lip = trimesh.creation.box(extents=(w, t, lip_h))
    lip.apply_translation((0, -d/2 + t/2, lip_h/2))

    mesh = trimesh.util.concatenate([base, back, lip])
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
