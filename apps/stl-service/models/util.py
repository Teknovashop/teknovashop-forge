# apps/stl-service/models/util.py
# Utilidades comunes para generar sólidos y taladrar con trimesh (sin OpenSCAD)

import math
import numpy as np
import trimesh as tm

def _cyl_transform_at(x: float, y: float, z: float, axis: str):
    """
    Matriz 4x4 que orienta un cilindro (por defecto alineado a +Z)
    al eje indicado y lo coloca en (x,y,z).
    """
    axis = (axis or "y").lower()
    if axis == "z":
        R = np.eye(3)
    elif axis == "x":
        # rotar Z->X: Ry(-90º)
        R = tm.transformations.rotation_matrix(-math.pi / 2, [0, 1, 0])[:3, :3]
    else:  # 'y'
        # rotar Z->Y: Rx(+90º)
        R = tm.transformations.rotation_matrix(+math.pi / 2, [1, 0, 0])[:3, :3]

    T = np.eye(4)
    T[:3, :3] = R
    T[:3,  3] = [x, y, z]
    return T

def long_enough(lengths, margin: float = 4.0) -> float:
    """Longitud suficiente para atravesar el bbox completo."""
    L, H, W = lengths
    return float(max(L, H, W) + margin)

def drill_holes(mesh: tm.Trimesh, holes: list, bbox_lengths):
    """
    Resta cilindros a 'mesh' según lista de agujeros con:
      {x_mm, y_mm, z_mm, d_mm, axis}
    - Si no hay 'y_mm' se usa el centroide del sólido en Y.
    - 'axis' por defecto: 'y'
    """
    if not holes:
        return mesh

    through = long_enough(bbox_lengths, margin=6.0)
    cyls = []

    # centro en Y por defecto
    cy = float(mesh.bounds[:, 1].mean()) if mesh.bounds.size else 0.0

    for h in holes:
        d = float(h.get("d_mm", 5.0))
        r = max(0.1, d / 2.0)
        axis = str(h.get("axis", "y")).lower()
        x = float(h.get("x_mm", 0.0))
        y = float(h.get("y_mm", cy))
        z = float(h.get("z_mm", 0.0))

        c = tm.creation.cylinder(radius=r, height=through, sections=48)
        c.apply_transform(_cyl_transform_at(x, y, z, axis))
        cyls.append(c)

    union_cyl = tm.util.concatenate(cyls) if len(cyls) > 1 else cyls[0]

    # ❌ Nada de engine="scad" – evita dependencia de OpenSCAD
    out = mesh.difference(union_cyl)
    return out

def box(L: float, H: float, W: float, center=(0.0, 0.0, 0.0)) -> tm.Trimesh:
    m = tm.creation.box(extents=[L, H, W])
    m.apply_translation(center)
    return m

def plate(L: float, W: float, T: float, y_bottom: float = 0.0) -> tm.Trimesh:
    """Placa centrada en XZ, apoyada en y_bottom."""
    return box(L, T, W, center=(0.0, y_bottom + T / 2.0, 0.0))

def shell_box(L: float, H: float, W: float, wall: float) -> tm.Trimesh:
    """Caja hueca: outer - inner (sin tapa modelada)."""
    outer = box(L, H, W, center=(0.0, H / 2.0, 0.0))
    inner = box(L - 2 * wall, H - wall, W - 2 * wall,
                center=(0.0, (H - wall) / 2.0, 0.0))
    # ❌ Sin engine="scad"
    return outer.difference(inner)
