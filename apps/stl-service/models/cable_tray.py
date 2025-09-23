# apps/stl-service/models/cable_tray.py
from typing import Dict, Any
import trimesh
from ._helpers import parse_holes
from .utils_geo import rectangle_plate, plate_with_holes, concatenate

NAME = "cable_tray"

TYPES = {
    "width": "float",       # separación entre laterales (profundidad de la bandeja)
    "height": "float",      # altura de los laterales
    "length": "float",      # largo
    "thickness": "float",   # espesor chapa
    "ventilated": "bool",   # si True, ranuras en la base
    "holes": "list[tuple[float, float, float], tuple[float, float, float]]",  # agujeros en el lateral izquierdo (x,y,d) y derecho (x,y,d)
}

DEFAULTS = {
    "width": 60.0,
    "height": 25.0,
    "length": 180.0,
    "thickness": 3.0,
    "ventilated": True,
    "holes": [],  # (x,y,d) relativo al lateral (placa vertical)
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    W = float(params.get("width", DEFAULTS["width"]))
    H = float(params.get("height", DEFAULTS["height"]))
    L = float(params.get("length", DEFAULTS["length"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    holes = parse_holes(params.get("holes", []))
    ventilated = bool(params.get("ventilated", DEFAULTS["ventilated"]))

    # Dos laterales (placas verticales) + base inferior (placa horizontal).
    left = rectangle_plate(L, H, T, holes)              # lateral izquierdo
    right = rectangle_plate(L, H, T, holes)             # reutilizamos mismos agujeros
    right.apply_translation((0, 0, W))                  # separarlo por el ancho

    # Base: placa horizontal con posibles ranuras “simuladas” como agujeros grandes (opcional)
    base_holes = []
    if ventilated:
        # Colocamos “ventanas” circulares a lo largo del centro solo para alivianar.
        n = max(1, int(L // 30))
        step = L / (n + 1)
        x0 = -L / 2.0 + step
        for i in range(n):
            base_holes.append((x0 + i * step, 0.0, min(8.0, W * 0.5)))

    base = plate_with_holes(L, W, T, base_holes)
    base.apply_translation((0, 0, W / 2.0))             # centrar en Z entre los laterales

    # Ensamblado
    tray = concatenate([left, right, base])
    return tray
