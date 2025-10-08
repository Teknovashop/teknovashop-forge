# apps/stl-service/models/headset_stand.py
from typing import Dict, Any, List, Tuple
import math
import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from .utils_geo import plate_with_holes, rectangle_plate, concatenate
from ._helpers import parse_holes

NAME = "headset_stand"

# Usamos el contrato genérico: length_mm, width_mm, height_mm, thickness_mm, fillet_mm
DEFAULTS: Dict[str, float] = {
    "length_mm": 120.0,   # largo de la base (X)
    "width_mm": 80.0,     # fondo de la base (Z)
    "height_mm": 260.0,   # altura del mástil
    "thickness_mm": 4.0,  # espesor de placas
    "fillet_mm": 6.0      # radio suave en transiciones (estético, aproximado)
}

TYPES: Dict[str, str] = {
    "length_mm": "float",
    "width_mm": "float",
    "height_mm": "float",
    "thickness_mm": "float",
    "fillet_mm": "float",
    "holes": "list[tuple[float,float,float]]"
}

def _u_yoke(inner_radius: float, width: float, thickness: float) -> trimesh.Trimesh:
    """
    Genera una 'horquilla' en U para apoyar la diadema.
    Se aproxima con 2 cilindros laterales + un puente rectangular curvado.
    """
    r = inner_radius
    w = width
    t = thickness

    # dos columnas (cilindros) a cada lado
    col = cylinder(radius=t/2.0, height=w, sections=64)
    col.apply_rotation(trimesh.transformations.rotation_matrix(math.pi/2, [1,0,0]))
    c1 = col.copy(); c1.apply_translation((+r, 0, 0))
    c2 = col.copy(); c2.apply_translation((-r, 0, 0))

    # puente superior (caja curvada aproximada con una caja)
    bridge = box(extents=(2*r + t, t, w))
    bridge.apply_translation((0, r, 0))

    u = concatenate([c1, c2, bridge])
    # elevar un poco para sentar sobre el mástil
    u.apply_translation((0, 0, 0))
    return u

def make_model(params: Dict[str, Any], holes: List[Tuple[float, float, float]] = ()) -> trimesh.Trimesh:
    L = float(params.get("length_mm", DEFAULTS["length_mm"]))
    W = float(params.get("width_mm", DEFAULTS["width_mm"]))
    H = float(params.get("height_mm", DEFAULTS["height_mm"]))
    T = float(params.get("thickness_mm", DEFAULTS["thickness_mm"]))
    F = float(params.get("fillet_mm", DEFAULTS["fillet_mm"]))

    # Base rectangular con agujeros opcionales para atornillar (x,z,d) en el plano
    hxz = parse_holes(holes) if holes else []
    base = plate_with_holes(L, W, T, hxz)

    # Mástil: placa vertical (X por Y = altura), centrado en X, colocado en el fondo
    mast = rectangle_plate(T * 3, H, T)  # mástil delgado, 3T de ancho
    mast.apply_translation((0, T + H/2.0, -W/2.0 + T*2))

    # Yoke superior: ancho ~ L*0.6, radio interior ~ L*0.25
    y_w = L * 0.6
    y_r = L * 0.25
    yoke = _u_yoke(y_r, y_w, T)
    # Colocar el yoke en la cima del mástil
    yoke.apply_translation((0, T + H, -W/2.0 + T*2))

    mesh = concatenate([base, mast, yoke])
    # Centrar en torno al origen: ya está centrado en X, adelantado en +Y (espesor)
    return mesh