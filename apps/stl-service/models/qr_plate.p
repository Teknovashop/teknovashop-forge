import math
import trimesh as tm

def _holes_cylinders(holes, thickness):
    cs = []
    for h in holes or []:
        d = float(h.get("d_mm", 5))
        x = float(h.get("x_mm", 0))
        z = float(h.get("z_mm", 0))
        r = max(0.1, d/2.0)
        c = tm.creation.cylinder(radius=r, height=thickness*3, sections=32, transform=tm.transformations.rotation_matrix(math.pi/2, (1,0,0)))
        c.apply_translation((x, thickness*1.5, z))
        cs.append(c)
    return cs

def make_model(p: dict) -> tm.Trimesh:
    # params: length, width, thickness, slot_mm, screw_d_mm, holes:[]
    L = float(p.get("length", 90))
    W = float(p.get("width", 38))
    T = float(p.get("thickness", 8))
    slot = float(p.get("slot_mm", 22))
    screw_d = float(p.get("screw_d_mm", 6.5))

    plate = tm.creation.box((L, T, W))
    plate.apply_translation((L/2, T/2, W/2))

    # ranura longitudinal centrada
    cut = tm.creation.box((slot, T*2, W*0.4))
    cut.apply_translation((L/2, T, W/2))
    body = plate.difference(cut, engine="scad" if tm.interfaces.solid.is_available() else None)

    # tres tornillos guía (solo marcadores; no atraviesan por defecto)
    for i in (-L*0.25, L*0.0, L*0.25):
      cyl = tm.creation.cylinder(radius=screw_d/2, height=T*3, sections=32, transform=tm.transformations.rotation_matrix(math.pi/2, (1,0,0)))
      cyl.apply_translation((L/2+i, T*1.5, W/2))
      body = body.difference(cyl, engine="scad" if tm.interfaces.solid.is_available() else None)

    # agujeros libres
    for cyl in _holes_cylinders(p.get("holes"), T):
        body = body.difference(cyl, engine="scad" if tm.interfaces.solid.is_available() else None)

    return body
