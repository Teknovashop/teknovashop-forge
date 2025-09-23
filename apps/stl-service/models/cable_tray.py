# apps/stl-service/models/cable_tray.py
from typing import Iterable, Tuple, List
import trimesh as tm
from .utils_geo import plate_with_holes, rectangle_plate, concatenate

def make_model(p: dict) -> tm.Trimesh:
    W   = float(p.get("width", 60.0))     # Z
    H   = float(p.get("height", 25.0))    # Y
    L   = float(p.get("length", 180.0))   # X
    T   = float(p.get("thickness", 3.0))
    vent= bool(p.get("ventilated", True))
    free: Iterable[Tuple[float,float,float]] = p.get("holes") or []

    # Base con agujeros libres
    base = plate_with_holes(L=L, W=W, T=T, holes=[(float(x), float(z), float(d)) for (x,z,d) in free])
    base.apply_translation((0, 0, 0))  # centrada sobre X/Z, apoyada en Y=0 por util

    # Laterales
    side_holes: List[Tuple[float, float, float]] = []
    if vent:
        pitch_x = 18.0
        d = 4.0
        xs = [x for x in range(-int(L//2), int(L//2)+1, int(pitch_x))]
        y_rows = [H*0.35, H*0.7]
        for y in y_rows:
            for x in xs:
                side_holes.append((float(x), float(y), d))

    left  = rectangle_plate(L=L, H=H, T=T, holes=side_holes).copy()
    right = rectangle_plate(L=L, H=H, T=T, holes=side_holes).copy()
    # colocar a ±W/2
    left.apply_translation((0, H/2.0, +W/2.0))
    right.apply_translation((0, H/2.0, -W/2.0))

    return concatenate([base, left, right])
