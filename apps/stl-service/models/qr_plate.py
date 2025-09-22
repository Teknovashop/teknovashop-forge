# apps/stl-service/models/qr_plate.py
from typing import Dict, Any, Iterable, Tuple, List
import shapely.geometry as sg
import shapely.ops as so
import trimesh
from .utils_geo import plate_with_holes, slot

def make_model(
    length: float = 90.0,
    width: float = 38.0,
    thickness: float = 8.0,
    slot_mm: float = 22.0,       # longitud ranura central
    screw_d_mm: float = 6.5,     # Ø de tornillos extremos
    holes: Iterable[Dict[str, float]] = (),
) -> trimesh.Trimesh:
    # ranura central tipo cápsula a lo largo del eje X
    # la hacemos restando de la placa como dos círculos conectados
    # -> la helper plate_with_holes solo hace circulares, así que
    # construimos el polígono a mano y extruimos:
    L, W, T = length, width, thickness
    outer = sg.box(-L/2, -W/2, L/2, W/2)

    # slot centrado a lo largo de X
    ran = slot(0.0, 0.0, slot_mm, screw_d_mm * 1.2)    # algo más ancho que el tornillo
    # agujeros extra (circulares)
    circles = [sg.Point(h["x_mm"], h["z_mm"]).buffer(h["d_mm"]/2.0, resolution=64) for h in holes]
    interior = so.unary_union([ran] + circles) if (holes or True) else ran
    poly = outer.difference(interior)

    mesh = trimesh.creation.extrude_polygon(poly, T)
    mesh.apply_translation((0, T/2.0, 0))
    return mesh
