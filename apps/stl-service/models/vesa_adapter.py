# apps/stl-service/models/vesa_adapter.py
from typing import Iterable, Tuple, List
import math
import trimesh as tm
from .utils_geo import plate_with_holes

def _vesa_pattern(vesa_mm: float, hole: float) -> List[Tuple[float, float, float]]:
    s = float(vesa_mm) / 2.0
    return [(+s, +s, hole), (-s, +s, hole), (+s, -s, hole), (-s, -s, hole)]

def make_model(p: dict) -> tm.Trimesh:
    vesa_mm = float(p.get("vesa_mm", 100.0))
    t       = float(p.get("thickness", 4.0))
    clr     = float(p.get("clearance", 1.0))
    hole_d  = float(p.get("hole", 5.0))

    # placa cuadrada con algo de margen respecto al patrón
    L = W = vesa_mm + 2.0 * max(10.0, clr * 5.0)

    auto = _vesa_pattern(vesa_mm, hole_d)
    free: Iterable[Tuple[float, float, float]] = p.get("holes") or []
    holes = [*auto, *[(float(x), float(z), float(d)) for (x, z, d) in free]]

    return plate_with_holes(L=L, W=W, T=t, holes=holes)
