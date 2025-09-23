# apps/stl-service/models/phone_stand.py
from typing import Dict, Any
import math
import trimesh

NAME = "phone_stand"

TYPES = {
    "angle_deg": "float",     # SOLO informativo por ahora (no rotamos geometría para evitar CSG); lo dejamos en la UI
    "angle": "float",         # idem (mantener compatibilidad con UI antigua)
    "support_depth": "float", # fondo de la base
    "depth": "float",         # alias para compatibilidad
    "width": "float",
    "thickness": "float",
}

DEFAULTS = {
    "angle_deg": 60.0,
    "angle": 60.0,
    "support_depth": 110.0,
    "depth": None,
    "width": 80.0,
    "thickness": 4.0,
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    depth = params.get("support_depth", None)
    if depth is None:
        depth = params.get("depth", DEFAULTS["support_depth"])
    D = float(depth)
    W = float(params.get("width", DEFAULTS["width"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    # Base rectangular estable (sin ángulos) para fiabilidad de STL.
    base = trimesh.creation.box(extents=(D, T, W))
    base.apply_translation((0, T / 2.0, 0))
    return base
