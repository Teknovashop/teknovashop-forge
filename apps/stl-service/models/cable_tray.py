# apps/stl-service/models/cable_tray.py
import trimesh
from trimesh.transformations import translation_matrix as T

def make_model(p: dict) -> trimesh.Trimesh:
    """
    Canal en U: X=length, Y=height, Z=width.
    """
    L = float(p.get("length", 180))
    H = float(p.get("height", 25))
    W = float(p.get("width",  60))
    TCK = float(p.get("thickness", 3))
    ventilated = bool(p.get("ventilated", True))

    base = trimesh.creation.box(extents=[L, TCK, W]);         base.apply_transform(T([0, -H/2 + TCK/2, 0]))
    side1= trimesh.creation.box(extents=[L, H, TCK]);         side1.apply_transform(T([0, 0, -W/2 + TCK/2]))
    side2= trimesh.creation.box(extents=[L, H, TCK]);         side2.apply_transform(T([0, 0,  W/2 - TCK/2]))

    parts=[base, side1, side2]

    if ventilated:
        # listones superficiales (decorativos; sin CSG)
        n = max(3, int(L // 40))
        gap = L / (n + 1)
        rib_w = max(2.0, min(6.0, W * 0.08))
        for i in range(1, n+1):
            rib = trimesh.creation.box(extents=[rib_w, TCK * 1.05, W - 2*TCK])
            rib.apply_transform(T([-L/2 + i*gap, -H/2 + TCK/2 + 0.01, 0]))
            parts.append(rib)

    return trimesh.util.concatenate(parts)
