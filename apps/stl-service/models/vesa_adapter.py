# teknovashop-forge/models/vesa_adapter.py
import trimesh
from trimesh.transformations import translation_matrix as T

def _drill(mesh: trimesh.Trimesh, holes: list, tck: float) -> trimesh.Trimesh:
    if not holes:
        return mesh
    cutters = []
    h = tck * 1.8
    for hspec in holes:
        x = float(hspec.get("x_mm", 0.0))
        z = float(hspec.get("z_mm", 0.0))
        d = max(0.1, float(hspec.get("d_mm", 3.0)))
        cyl = trimesh.creation.cylinder(radius=d/2.0, height=h, sections=48)
        cyl.apply_transform(T([x, 0.0, z]))
        cutters.append(cyl)
    if cutters:
        cutter = trimesh.util.concatenate(cutters)
        try:
            return mesh.difference(cutter, engine="scad")
        except BaseException:
            return mesh.difference(cutter)
    return mesh

def make_model(p: dict) -> trimesh.Trimesh:
    V   = float(p.get("vesa_mm", 100.0))
    TCK = float(p.get("thickness", 4.0))
    CLR = float(p.get("clearance", 1.0))
    HOLE= float(p.get("hole", 5.0)) / 2.0
    extra = p.get("holes") or []

    size = V + 2*CLR + 20.0
    plate = trimesh.creation.box(extents=[size, TCK, size])

    # 4 agujeros VESA
    h = TCK*1.6
    cyl = trimesh.creation.cylinder(radius=HOLE, height=h, sections=36)
    off = V/2.0
    holes=[]
    for x in (+off,-off):
        for z in (+off,-off):
            c=cyl.copy(); c.apply_transform(T([x,0,z])); holes.append(c)

    mesh = trimesh.util.concatenate([plate,*holes])
    mesh = _drill(mesh, extra, TCK)  # extra holes del usuario
    mesh.remove_duplicate_faces(); mesh.remove_degenerate_faces(); mesh.merge_vertices()
    return mesh
