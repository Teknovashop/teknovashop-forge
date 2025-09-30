# apps/stl-service/models/_ops.py
import math
import trimesh
from trimesh.creation import cylinder, box
from ._booleans import boolean_diff, boolean_union


def cut_hole(mesh: trimesh.Trimesh, x_mm: float, y_mm: float, z_mm: float, d_mm: float, axis: str = "z") -> trimesh.Trimesh:
    r = max(0.1, d_mm / 2.0)
    h = max(mesh.bounds[1][2] - mesh.bounds[0][2], 1.0) * 4.0  # cilindro alto
    cyl = cylinder(radius=r, height=h, sections=48)
    # orientado
    if axis == "x":
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
    elif axis == "y":
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1,0,0]))
    # situar
    bb_min, bb_max = mesh.bounds
    if axis == "z":
        base = (x_mm, y_mm, bb_min[2] - h*0.25)
    elif axis == "x":
        base = (bb_min[0] - h*0.25, y_mm, z_mm)
    else:
        base = (x_mm, bb_min[1] - h*0.25, z_mm)
    cyl.apply_translation(base)
    return boolean_diff(mesh, cyl)


def cut_box(mesh: trimesh.Trimesh, center, size) -> trimesh.Trimesh:
    """
    Corte rectangular (ranura/cajeado). center=(x,y,z), size=(sx,sy,sz)
    """
    sx, sy, sz = [max(0.1, float(v)) for v in size]
    b = box(extents=(sx, sy, sz))
    b.apply_translation(center)
    return boolean_diff(mesh, b)


def round_edges_box(extents, radius: float) -> trimesh.Trimesh:
    """
    Caja con “fillet” simple aproximado por unión de caja + 8 cilindros verticales (esquinas).
    No es un fillet paramétrico perfecto, pero produce resultados suaves y printable-friendly.
    """
    L, W, H = [float(v) for v in extents]
    r = max(0.0, float(radius))
    core = box(extents=(L - 2*r, W - 2*r, H)) if r > 0 else box(extents=(L, W, H))
    core.apply_translation((0, 0, H/2))
    if r <= 0:
        return core

    # 4 esquinas superiores e inferiores con “postes” (cilindros) fusionados
    add = core
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = sx * (L/2 - r)
            cy = sy * (W/2 - r)
            col = cylinder(radius=r, height=H, sections=64)
            col.apply_translation((cx, cy, H/2))
            add = boolean_union(add, col)

    return add
