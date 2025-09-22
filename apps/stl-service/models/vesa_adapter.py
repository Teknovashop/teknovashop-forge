# apps/stl-service/models/vesa_adapter.py
from typing import Iterable, Dict, Any
import trimesh
from .utils_geo import plate_with_holes

def make_model(
    vesa_mm: float = 100.0,
    thickness: float = 4.0,
    clearance: float = 1.0,
    vesa_hole: float = 5.0,
    extra_holes: Iterable[Dict[str, float]] = (),
) -> trimesh.Trimesh:
    L = W = vesa_mm + clearance * 2.0
    # agujeros patrón VESA
    off = vesa_mm / 2.0
    vesa = [(+off, +off, vesa_hole), (+off, -off, vesa_hole), (-off, +off, vesa_hole), (-off, -off, vesa_hole)]
    # extra
    extras = [(h["x_mm"], h["z_mm"], h["d_mm"]) for h in extra_holes]
    holes = vesa + extras
    return plate_with_holes(L=L, W=W, T=thickness, holes=holes)
