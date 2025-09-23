# apps/stl-service/models/vesa_adapter.py
from typing import Dict, Any, List, Tuple
import trimesh
from ._helpers import parse_holes
from .utils_geo import plate_with_holes

NAME = "vesa_adapter"

TYPES: Dict[str, str] = {
    "vesa_mm": "float",        # separación entre centros de los 4 tornillos (100, 75, etc.)
    "thickness": "float",      # espesor de la placa
    "clearance": "float",      # margen alrededor (placa más grande que el patrón)
    "hole": "float",           # diámetro de los agujeros VESA
    "holes": "list[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]",
}

DEFAULTS: Dict[str, Any] = {
    "vesa_mm": 100.0,
    "thickness": 5.0,
    "clearance": 10.0,
    "hole": 5.0,
    "holes": None,  # si no viene, los generamos automáticamente a partir de vesa_mm y hole
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    vesa = float(params.get("vesa_mm", DEFAULTS["vesa_mm"]))
    t = float(params.get("thickness", DEFAULTS["thickness"]))
    c = float(params.get("clearance", DEFAULTS["clearance"]))
    h = float(params.get("hole", DEFAULTS["hole"]))

    L = W = vesa + 2.0 * c  # placa cuadrada
    # agujeros: centrados ±vesa/2
    holes_in = params.get("holes")
    if holes_in:
        holes = parse_holes(holes_in)
    else:
        s = vesa / 2.0
        holes = [( s,  s, h), (-s,  s, h), ( s, -s, h), (-s, -s, h)]

    mesh = plate_with_holes(L, W, t, holes)
    return mesh
