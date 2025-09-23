# apps/stl-service/models/qr_plate.py
from typing import Dict, Any
import trimesh
from ._helpers import parse_holes
from .utils_geo import plate_with_holes, slot

NAME = "qr_plate"

TYPES = {
    "length": "float",     # largo (X)
    "width": "float",      # ancho (Z en vista XY de la placa)
    "thickness": "float",  # espesor (Y+)
    "slot_mm": "float",    # separación entre los dos agujeros extremos (centro a centro)
    "screw_d_mm": "float", # diámetro de tornillo
    "holes": "list[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]",
}

DEFAULTS = {
    "length": 90.0,
    "width": 38.0,
    "thickness": 8.0,
    "slot_mm": 22.0,
    "screw_d_mm": 6.5,
    "holes": None,  # si viene, se usa; si no, generamos 3 agujeros: 0 y ±slot/2 sobre el eje X
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(params.get("length", DEFAULTS["length"]))
    W = float(params.get("width", DEFAULTS["width"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    slot_mm = float(params.get("slot_mm", DEFAULTS["slot_mm"]))
    d = float(params.get("screw_d_mm", DEFAULTS["screw_d_mm"]))

    if params.get("holes") is not None:
        holes = parse_holes(params["holes"])
    else:
        s = slot_mm / 2.0
        holes = [(0.0, 0.0, d), ( s, 0.0, d), (-s, 0.0, d)]

    return plate_with_holes(L, W, T, holes)
