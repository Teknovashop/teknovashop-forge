# models/vesa_adapter.py
from typing import Dict, List, Tuple
from utils.stl_writer import Tri, add_box, add_cylinder_z, triangles_to_stl

def build(params: Dict) -> bytes:
    # Parámetros
    plate_w   = float(params.get("plate_w", 120.0))  # mm
    plate_h   = float(params.get("plate_h", 120.0))  # mm
    plate_t   = float(params.get("plate_t", 5.0))    # mm
    vesa      = int(params.get("vesa", 75))          # 75, 100, 200...
    boss_d    = float(params.get("boss_d", 6.0))     # diámetro tetón
    boss_h    = float(params.get("boss_h", 2.0))     # altura tetón

    tris: List[Tri] = []
    # Placa centrada en Z=plate_t/2
    add_box(tris, 0, 0, plate_t/2, plate_w, plate_h, plate_t)

    # 4 tetones guía en patrón VESA (medida entre centros)
    off = vesa/2.0
    for (x,y) in [( off,  off), ( off, -off), (-off,  off), (-off, -off)]:
        add_cylinder_z(tris, x, y, plate_t, plate_t+boss_h, boss_d/2.0, segments=40)

    return triangles_to_stl("vesa_adapter", tris)
