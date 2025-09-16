# apps/stl-service/models/vesa_adapter.py
import trimesh
from trimesh.transformations import translation_matrix as T

def make_model(p: dict) -> trimesh.Trimesh:
    V   = float(p.get("vesa_mm", 100.0))
    TCK = float(p.get("thickness", 4.0))
    CLR = float(p.get("clearance", 1.0))
    HOLE= float(p.get("hole", 5.0)) / 2.0

    size = V + 2*CLR + 20.0
    plate = trimesh.creation.box(extents=[size, TCK, size])

    h = TCK*1.4
    cyl = trimesh.creation.cylinder(radius=HOLE, height=h, sections=24)
    off = V/2.0
    holes=[]
    for x in (+off,-off):
        for z in (+off,-off):
            c=cyl.copy(); c.apply_transform(T([x,0,z])); holes.append(c)

    return trimesh.util.concatenate([plate,*holes])
