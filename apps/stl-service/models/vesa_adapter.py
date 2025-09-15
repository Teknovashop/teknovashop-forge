# apps/stl-service/models/vesa_adapter.py
import math
import trimesh
from trimesh.transformations import translation_matrix as T

def make_model(p: dict) -> trimesh.Trimesh:
    """
    Placa cuadrada (VESA) con cilindros “marcadores” de agujero.
    Si quieres agujeros reales, habría que hacer CSG (resta) con un backend booleano.
    """
    V   = float(p.get("vesa_mm", 100.0))
    TCK = float(p.get("thickness", 4.0))
    CLR = float(p.get("clearance", 1.0))
    # margen visual exterior
    size = V + 2*CLR + 20.0

    plate = trimesh.creation.box(extents=[size, TCK, size])

    # “Agujeros” como cilindros (decorativos)
    r = float(p.get("hole", 5.0)) / 2.0
    hole_h = TCK * 1.4
    cyl = trimesh.creation.cylinder(radius=r, height=hole_h, sections=24)

    off = V/2.0
    h1 = cyl.copy(); h1.apply_transform(T([+off, 0, +off]))
    h2 = cyl.copy(); h2.apply_transform(T([-off, 0, +off]))
    h3 = cyl.copy(); h3.apply_transform(T([+off, 0, -off]))
    h4 = cyl.copy(); h4.apply_transform(T([-off, 0, -off]))

    mesh = trimesh.util.concatenate([plate, h1, h2, h3, h4])
    return mesh
