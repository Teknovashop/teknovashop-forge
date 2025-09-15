# apps/stl-service/models/router_mount.py
import trimesh
from trimesh.transformations import translation_matrix as T

def make_model(p: dict) -> trimesh.Trimesh:
    """
    Escuadra en L: base + pared.
    router_width → X (ancho), router_depth → Z (fondo), height se calcula si no viene.
    """
    W    = float(p.get("router_width", 120))
    D    = float(p.get("router_depth", 80))
    TCK  = float(p.get("thickness", 4))
    H    = float(p.get("height", D * 0.6))  # altura pared por defecto

    base = trimesh.creation.box(extents=[W, TCK, D])
    base.apply_transform(T([0, -D*0.3, 0]))

    wall = trimesh.creation.box(extents=[W, H, TCK])
    wall.apply_transform(T([0, 0, -D/2 + TCK/2]))

    mesh = trimesh.util.concatenate([base, wall])
    return mesh
