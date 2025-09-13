# models/cable_tray.py
from typing import Dict, List
from utils.stl_writer import Tri, add_box, triangles_to_stl

def build(params: Dict) -> bytes:
    length    = float(params.get("length", 180.0))
    inner_w   = float(params.get("inner_w", 20.0))
    inner_h   = float(params.get("inner_h", 15.0))
    wall_t    = float(params.get("wall_t", 2.5))
    base_t    = float(params.get("base_t", 3.0))

    tris: List[Tri] = []
    # Base
    add_box(tris, 0, 0, base_t/2, length, inner_w + 2*wall_t, base_t)
    # Pared izquierda
    add_box(tris, 0,  (inner_w/2 + wall_t/2), (base_t + inner_h/2), length, wall_t, inner_h)
    # Pared derecha
    add_box(tris, 0, -(inner_w/2 + wall_t/2), (base_t + inner_h/2), length, wall_t, inner_h)

    return triangles_to_stl("cable_tray", tris)
