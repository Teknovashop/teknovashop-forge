# apps/stl-service/models/cable_clip.py
from typing import Dict, Any
import trimesh
from .utils_geo import plate_with_holes

NAME = "cable_clip"

TYPES = {
    "diameter": "float",   # d del cable
    "width": "float",      # ancho de la lengüeta
    "thickness": "float",  # espesor
}

DEFAULTS = {
    "diameter": 8.0,
    "width": 12.0,
    "thickness": 2.4,
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    d = float(params.get("diameter", DEFAULTS["diameter"]))
    W = float(params.get("width", DEFAULTS["width"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    # Simplificación robusta: plaquita con agujero de paso del cable (puede atornillarse aparte)
    L = max(18.0, d * 2.2)
    holes = [(0.0, 0.0, d)]
    return plate_with_holes(L, W, T, holes)
