# apps/stl-service/models/mic_arm_clip.py
from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "mic_arm_clip"

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
    # UI: arm_d, opening, clip_t, width, wall
    arm_d = float(params.get("arm_d", 20.0))
    gap = float(params.get("opening", 0.6))
    clip_t = float(params.get("clip_t", 3.0))
    w = float(params.get("width", 14.0))
    wall = float(params.get("wall", 3.0))

    r_out = arm_d/2 + wall
    r_in  = max(arm_d/2 - 0.01, 0.1)  # evitar negativo

    # tubo (anillo) extruido
    outer = trimesh.creation.cylinder(radius=r_out, height=w, sections=96)
    inner = trimesh.creation.cylinder(radius=r_in,  height=w*1.2, sections=96)
    ring = _bool_diff(outer, inner)

    # abertura: corte rectangular del ancho 'gap'
    slit = trimesh.creation.box(extents=(gap, r_out*2.2, w*1.3))
    slit.apply_translation((r_out - gap/2, 0, w/2))
    ring = _bool_diff(ring, slit)

    # aleta/refuerzo
    fin = trimesh.creation.box(extents=(clip_t, r_out*1.2, w))
    fin.apply_translation((-(r_out + clip_t/2), 0, w/2))

    return trimesh.util.concatenate([ring, fin])

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
