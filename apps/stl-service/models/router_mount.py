# teknovashop-forge/models/router_mount.py
import trimesh
from trimesh.transformations import translation_matrix as T

def _drill(mesh: trimesh.Trimesh, holes: list, tck: float, base_y: float) -> trimesh.Trimesh:
    if not holes: 
        return mesh
    cutters=[]
    h=tck*2.2
    for hspec in holes:
        x = float(hspec.get("x_mm", 0.0))
        z = float(hspec.get("z_mm", 0.0))
        d = max(0.1, float(hspec.get("d_mm", 3.0)))
        cyl = trimesh.creation.cylinder(radius=d/2.0, height=h, sections=48)
        # taladro sobre la base (aprox a y = base_y)
        cyl.apply_transform(T([x, base_y, z]))
        cutters.append(cyl)
    if cutters:
        cutter=trimesh.util.concatenate(cutters)
        try:
            return mesh.difference(cutter, engine="scad")
        except BaseException:
            return mesh.difference(cutter)
    return mesh

def make_model(p: dict) -> trimesh.Trimesh:
    W   = float(p.get("router_width", 120))
    D   = float(p.get("router_depth", 80))
    TCK = float(p.get("thickness", 4))
    H   = float(p.get("height", D*0.6))
    holes = p.get("holes") or []

    base = trimesh.creation.box(extents=[W, TCK, D]); base.apply_transform(T([0, -D*0.3, 0]))
    wall = trimesh.creation.box(extents=[W, H, TCK]); wall.apply_transform(T([0, 0, -D/2 + TCK/2]))

    mesh = trimesh.util.concatenate([base, wall])
    mesh = _drill(mesh, holes, TCK, base_y=-D*0.3)
    mesh.remove_duplicate_faces(); mesh.remove_degenerate_faces(); mesh.merge_vertices()
    return mesh
