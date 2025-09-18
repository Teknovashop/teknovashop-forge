# teknovashop-forge/models/router_mount.py
import trimesh
from trimesh.transformations import translation_matrix as T

def make_model(p: dict) -> trimesh.Trimesh:
    W   = float(p.get("router_width", 120))
    D   = float(p.get("router_depth", 80))
    TCK = float(p.get("thickness", 4))
    H   = float(p.get("height", D*0.6))

    base = trimesh.creation.box(extents=[W, TCK, D]); base.apply_transform(T([0, -D*0.3, 0]))
    wall = trimesh.creation.box(extents=[W, H, TCK]); wall.apply_transform(T([0, 0, -D/2 + TCK/2]))

    return trimesh.util.concatenate([base, wall])
