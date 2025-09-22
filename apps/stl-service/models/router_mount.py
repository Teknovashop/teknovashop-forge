# apps/stl-service/models/router_mount.py
from typing import Dict, Any, Iterable, List, Tuple
import trimesh
from .utils_geo import plate_with_holes, rectangle_plate, concatenate

def make_model(
    width: float = 120.0,     # W (ancho base)
    depth: float = 80.0,      # L (fondo base)
    flange: float = 60.0,     # ala vertical
    thickness: float = 4.0,
    ventilated: bool = True,
    holes: Iterable[Dict[str, float]] = (),
) -> trimesh.Trimesh:
    # Base (L=depth, W=width)
    base = plate_with_holes(L=depth, W=width, T=thickness,
                            holes=[(h["x_mm"], h["z_mm"], h["d_mm"]) for h in holes])
    # Ala (vertical, alto=flange, largo=depth)
    side_holes: List[Tuple[float, float, float]] = []
    if ventilated:
        # taladro Ø6 cada 15mm en 2 filas
        pitch = 15.0
        d = 6.0
        y_rows = [flange * 0.35, flange * 0.7]
        xs = [x for x in [i for i in range(-int(depth//2), int(depth//2)+1, int(pitch))]]
        for y in y_rows:
            for x in xs:
                side_holes.append((float(x), float(y), d))

    wing = rectangle_plate(L=depth, H=flange, T=thickness, holes=side_holes)
    # Posicionar ala pegada a uno de los lados (z = -width/2)
    wing.apply_translation((0, flange/2.0, -width/2.0))

    return concatenate([base, wing])
