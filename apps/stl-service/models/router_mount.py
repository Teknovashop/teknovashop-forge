# apps/stl-service/models/router_mount.py
from typing import Iterable, Tuple
import trimesh as tm
from .utils_geo import plate_with_holes, rectangle_plate, concatenate

def make_model(p: dict) -> tm.Trimesh:
    W   = float(p.get("router_width", 120.0))  # X de la placa trasera
    D   = float(p.get("router_depth", 80.0))   # X de la base
    T   = float(p.get("thickness", 4.0))
    free: Iterable[Tuple[float,float,float]] = p.get("holes") or []

    # Base (soporte horizontal, sobre el que se apoya el router)
    base = plate_with_holes(L=D, W=W, T=T, holes=[])  # agujeros suelen ir en la trasera
    # Trasera (vertical) con agujeros de fijación
    back = rectangle_plate(L=W, H=W*0.7, T=T, holes=[(float(x), float(y), float(d)) for (x,y,d) in []])  # sin auto
    # Colocar trasera al borde de la base (en X ~ 0)
    back.apply_translation((0, (W*0.7)/2.0, -W/2.0))  # atrás
    base.apply_translation((D/2.0, 0.0, 0.0))

    # Si el usuario añadió 'holes' (x,y,d) para la trasera, perfóralos
    if free:
        # convertir trasera en placa con agujeros (L=W, H=..., T=T)
        back = rectangle_plate(L=W, H=W*0.7, T=T, holes=[(float(x), float(y), float(d)) for (x,y,d) in free])
        back.apply_translation((0, (W*0.7)/2.0, -W/2.0))

    return concatenate([base, back])
