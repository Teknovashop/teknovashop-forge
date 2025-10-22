from __future__ import annotations
from typing import Dict, Any, List, Tuple
import trimesh

SLUGS = ["tablet-stand"]

def _num(p: Dict[str, Any], k: str, d: float) -> float:
    v = p.get(k, d)
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return float(d)

def _plate(L: float, W: float, T: float) -> trimesh.Trimesh:
    return trimesh.creation.box((L, W, T))

def _union(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    try:
        m = trimesh.util.concatenate(meshes)
        m.remove_duplicate_faces()
        return m
    except Exception:
        return meshes[0]

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = _num(params, "length_mm", 160)
    W = _num(params, "width_mm", 140)   # profundidad
    H = _num(params, "height_mm", 120)  # altura respaldo
    T = _num(params, "thickness_mm", 4)

    base = _plate(L, W, T)
    back = _plate(L, T, H)
    back.apply_translation((0.0, W/2 - T/2, H/2))

    lip_h = max(6.0, _num(params, "fillet_mm", 8))  # reutilizamos fillet como pestaña
    lip = _plate(L, T, lip_h)
    lip.apply_translation((0.0, -W/2 + T/2, lip_h/2))

    out = _union([base, back, lip])
    return out

BUILD = {"make": make}
