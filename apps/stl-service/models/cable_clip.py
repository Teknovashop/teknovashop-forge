# apps/stl-service/models/cable_clip.py
import math
import trimesh as tm

def make_model(p: dict) -> tm.Trimesh:
    D = float(p.get("diameter", 8))
    W = float(p.get("width", 12))
    T = float(p.get("thickness", 2.4))

    base = tm.creation.box((W*2.2, T*2.2, W)); base.apply_translation((W*1.1, T*1.1, W/2))

    r = D/2.0
    torus = tm.creation.cylinder(radius=r+T, height=W*1.5, sections=64,
                                 transform=tm.transformations.rotation_matrix(math.pi/2, (1,0,0)))
    torus.apply_translation((W*1.1, T*1.1, W/2))
    core  = tm.creation.cylinder(radius=r, height=W*2, sections=64,
                                 transform=tm.transformations.rotation_matrix(math.pi/2, (1,0,0)))
    core.apply_translation((W*1.1, T*1.1, W/2))

    shape = base.intersection(torus, engine="scad" if tm.interfaces.solid.is_available() else None)
    shape = shape.difference(core, engine="scad" if tm.interfaces.solid.is_available() else None)
    return shape
