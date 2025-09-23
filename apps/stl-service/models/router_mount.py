# apps/stl-service/models/router_mount.py
from typing import Dict, Any
import trimesh
from ._helpers import parse_holes
from .utils_geo import plate_with_holes

NAME = "router_mount"

TYPES = {
    "router_width": "float",   # X
    "router_depth": "float",   # Z (ancho de la placa)
    "thickness": "float",      # Y
    "holes": "list[]",         # cualquiera; se normaliza a (x,y,d)
}

DEFAULTS = {
    "router_width": 120.0,
    "router_depth": 80.0,
    "thickness": 4.0,
    "holes": [],
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(params.get("router_width", DEFAULTS["router_width"]))
    W = float(params.get("router_depth", DEFAULTS["router_depth"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    holes = parse_holes(params.get("holes", []))
    return plate_with_holes(L, W, T, holes)
