# apps/stl-service/models/laptop_stand.py
from __future__ import annotations

from typing import Dict, Any, List, Tuple
import math
import shapely.geometry as sg
import trimesh
from trimesh.transformations import rotation_matrix

from .utils_geo import plate_with_holes, rectangle_plate, concatenate
from ._helpers import parse_holes

NAME = "laptop_stand"

DEFAULTS: Dict[str, float] = {
    "length_mm": 250.0,   # longitud de apoyo (X)
    "width_mm": 230.0,    # profundidad total (Z)
    "height_mm": 120.0,   # elevación posterior (Y)
    "thickness_mm": 4.0,  # espesor de las piezas
    "fillet_mm": 4.0,
}

TYPES: Dict[str, str] = {
    "length_mm": "float",
    "width_mm": "float",
    "height_mm": "float",
    "thickness_mm": "float",
    "fillet_mm": "float",
    "holes": "list[tuple[float,float,float]]",
}

def _rib_tri_prism(W: float, H: float, T: float) -> trimesh.Trimesh:
    """
    Costilla lateral triangular:
      - Perfil en XY: (0,0) -> (0,H) -> (W, 0.6*H)
      - Se extruye T (a lo largo de +Z) y luego se rota +90º alrededor de Y
        para que el espesor T quede alineado con el eje X (costilla “fina” en X).
      - Finalmente se centra en Z y en X (espesor T simétrico).
    Resultado: prism con dimensiones aprox (X: T, Y: ~H, Z: ~W).
    """
    profile = sg.Polygon([(0.0, 0.0), (0.0, H), (W, 0.6 * H)])
    rib = trimesh.creation.extrude_polygon(profile, T)  # extruye en +Z

    # Rotar +90° en Y: el espesor (antes en Z) pasa a X.
    R = rotation_matrix(math.radians(90.0), [0, 1, 0])
    rib.apply_transform(R)

    # Re-centrar: espesor simétrico en X y centrar en Z
    rib.apply_translation((-T / 2.0, 0.0, -W / 2.0))
    return rib


def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Builder principal (firma compat con tu app: recibe SOLO un dict).
    """
    L = float(params.get("length_mm",   DEFAULTS["length_mm"]))   # X
    W = float(params.get("width_mm",    DEFAULTS["width_mm"]))    # Z
    H = float(params.get("height_mm",   DEFAULTS["height_mm"]))   # Y
    T = float(params.get("thickness_mm", DEFAULTS["thickness_mm"]))

    # Agujeros opcionales (si llegan)
    holes_in = params.get("holes") or []
    holes: List[Tuple[float, float, float]] = parse_holes(holes_in)

    # ---- Costillas laterales (dos triángulos extruidos) ----
    rib0 = _rib_tri_prism(W=W, H=H, T=T)  # centrada en Z, espesor centrado en X

    # Colocar costillas a los laterales:
    #   izquierda: centro en x = -L/2 + T/2
    #   derecha:   centro en x = +L/2 - T/2
    rib_left = rib0.copy()
    rib_left.apply_translation((-L / 2.0 + T / 2.0, 0.0, 0.0))

    rib_right = rib0.copy()
    rib_right.apply_translation((+L / 2.0 - T / 2.0, 0.0, 0.0))

    # ---- Superficie superior (apoyo del portátil) ----
    # rectangle_plate(L, ancho, T) -> placa con grosor T (eje Y en tus helpers)
    top = rectangle_plate(L, T * 2.0, T)
    # A la altura H y algo retrasada (como tenías)
    top.apply_translation((0.0, H, -W / 2.0 + W * 0.6))

    # ---- Labio frontal anti-deslizamiento ----
    lip = rectangle_plate(L, T * 1.5, T)
    lip.apply_translation((0.0, T * 1.5, -W / 2.0 + T * 2.0))

    # ---- Base trasera que une costillas (con agujeros opcionales) ----
    base = plate_with_holes(L, T * 2.5, T, holes)
    base.apply_translation((0.0, 0.0, W / 2.0 - T * 1.25))

    # ---- Ensamble final ----
    mesh = concatenate([rib_left, rib_right, top, lip, base])
    return mesh


# Alias para autodiscovery que acepte otros nombres
BUILD = {"make": make_model, "build": make_model}
__all__ = ["NAME", "DEFAULTS", "TYPES", "make_model", "BUILD"]
