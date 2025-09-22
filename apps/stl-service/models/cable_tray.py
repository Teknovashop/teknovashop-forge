# apps/stl-service/models/cable_tray.py
from typing import Dict, Any, Iterable, List, Tuple
import trimesh
from .utils_geo import plate_with_holes, rectangle_plate, concatenate

def make_model(
    width: float = 60.0,      # W (ancho útil)
    height: float = 25.0,     # H (alas)
    length: float = 180.0,    # L
    thickness: float = 3.0,
    ventilated: bool = True,
    holes: Iterable[Dict[str, float]] = (),
) -> trimesh.Trimesh:
    # Base con agujeros libres (x,z,d)
    base = plate_with_holes(L=length, W=width, T=thickness,
                            holes=[(h["x_mm"], h["z_mm"], h["d_mm"]) for h in holes])

    # Paredes laterales (placas verticales). Si ventilated, abrimos rejilla simple por slots.
    side_holes: List[Tuple[float, float, float]] = []
    if ventilated:
        # patrón: círculos Ø5mm cada 12mm en 2 filas
        pitch = 12.0
        d = 5.0
        y_rows = [height * 0.33, height * 0.66]
        xs = [x for x in [i for i in range(-int(length//2), int(length//2)+1, int(pitch))]]
        for y in y_rows:
            for x in xs:
                side_holes.append((float(x), float(y), d))

    side_L = length
    side_H = height
    wall_T = thickness

    left = rectangle_plate(L=side_L, H=side_H, T=wall_T,
                           holes=side_holes).copy()
    right = rectangle_plate(L=side_L, H=side_H, T=wall_T,
                            holes=side_holes).copy()

    # Posicionar paredes a ±W/2
    left.apply_translation((0, height/2.0, +width/2.0))
    right.apply_translation((0, height/2.0, -width/2.0))

    # Elevar base ligeramente para que quede al ras interior
    base.apply_translation((0, 0.0, 0))

    return concatenate([base, left, right])
