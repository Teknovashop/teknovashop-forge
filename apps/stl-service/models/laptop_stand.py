# apps/stl-service/models/laptop_stand.py
from typing import Dict, Any, List, Tuple
import math
import trimesh
from .utils_geo import plate_with_holes, rectangle_plate, concatenate
from ._helpers import parse_holes

NAME = "laptop_stand"

DEFAULTS: Dict[str, float] = {
    "length_mm": 250.0,   # longitud de apoyo
    "width_mm": 230.0,    # profundidad total
    "height_mm": 120.0,   # elevación posterior
    "thickness_mm": 4.0,
    "fillet_mm": 4.0
}

TYPES: Dict[str, str] = {
    "length_mm": "float",
    "width_mm": "float",
    "height_mm": "float",
    "thickness_mm": "float",
    "fillet_mm": "float",
    "holes": "list[tuple[float,float,float]]",
}

def make_model(params: Dict[str, Any], holes: List[Tuple[float, float, float]] = ()) -> trimesh.Trimesh:
    L = float(params.get("length_mm", DEFAULTS["length_mm"]))   # X
    W = float(params.get("width_mm", DEFAULTS["width_mm"]))     # Z
    H = float(params.get("height_mm", DEFAULTS["height_mm"]))   # Y
    T = float(params.get("thickness_mm", DEFAULTS["thickness_mm"]))

    # Dos costillas laterales en forma de triángulo (soporte en ángulo)
    side = trimesh.path.creation.random_walk()  # placeholder removed
    # Triángulo: (0,0), (0,H), (W, H*0.6) en plano YZ; lo extruimos en X = T
    import shapely.geometry as sg
    poly = sg.Polygon([(0,0), (0,H), (W, H*0.6)])
    rib = trimesh.creation.extrude_polygon(poly, T)
    rib.apply_translation(( -L/2.0, 0, -W/2.0 ))  # colocar a izquierda
    rib2 = rib.copy(); rib2.apply_translation((L - T, 0, 0))     # derecha

    # Superficie superior (apoyo del portátil)
    top = rectangle_plate(L, T*2, T)
    top.apply_translation((0, H, -W/2.0 + W*0.6))

    # Labio frontal para evitar deslizamiento
    lip = rectangle_plate(L, T*1.5, T)
    lip.apply_translation((0, T*1.5, -W/2.0 + T*2))

    # Base trasera que une costillas
    base = plate_with_holes(L, T*2.5, T, parse_holes(holes) if holes else [])
    base.apply_translation((0, 0, W/2.0 - T*1.25))

    mesh = concatenate([rib, rib2, top, lip, base])
    return mesh