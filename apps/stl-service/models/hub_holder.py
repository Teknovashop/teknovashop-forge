# apps/stl-service/models/hub_holder.py
from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "hub_holder"

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
    # UI: hub_w, hub_h, hub_d, tolerance, wall
    iw = float(params.get("hub_w", 100))
    ih = float(params.get("hub_h", 28))
    idp = float(params.get("hub_d", 30))
    tol = float(params.get("tolerance", 0.5))
    t = float(params.get("wall", 3))

    iw += 2*tol
    ih += 2*tol
    idp += 2*tol

    ow = iw + 2*t
    oh = ih + t
    odp = idp + t

    outer = trimesh.creation.box(extents=(ow, odp, oh))
    outer.apply_translation((0, 0, oh/2))

    inner = trimesh.creation.box(extents=(iw, idp, ih))
    inner.apply_translation((0, 0, t + ih/2))  # deja "suelo" de espesor t

    return _bool_diff(outer, inner)

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
