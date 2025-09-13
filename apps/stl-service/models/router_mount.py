# models/router_mount.py
from typing import Dict, List
from utils.stl_writer import Tri, add_box, triangles_to_stl

def build(params: Dict) -> bytes:
    inner_w   = float(params.get("inner_w", 32.0))   # ancho interior
    inner_h   = float(params.get("inner_h", 180.0))  # alto interior
    wall_t    = float(params.get("wall_t", 3.0))     # grosor paredes
    depth     = float(params.get("depth", 30.0))     # fondo U
    brim_t    = float(params.get("brim_t", 10.0))    # labio superior

    tris: List[Tri] = []

    # Pared trasera
    add_box(tris, 0, 0, wall_t/2, inner_w + 2*wall_t, inner_h + 2*wall_t, wall_t)
    # Pared izquierda
    add_box(tris, -(inner_w/2 + wall_t/2), 0, depth/2, wall_t, inner_h, depth)
    # Pared derecha
    add_box(tris,  (inner_w/2 + wall_t/2), 0, depth/2, wall_t, inner_h, depth)
    # Labio/ala superior
    add_box(tris, 0,  (inner_h/2 + wall_t/2), (depth+brim_t)/2, inner_w + 2*wall_t, wall_t, brim_t)

    return triangles_to_stl("router_mount", tris)
