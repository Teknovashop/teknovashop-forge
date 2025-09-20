# apps/stl-service/models/qr_plate.py
import math
import trimesh as tm

def _cyl(d, h):
    return tm.creation.cylinder(
        radius=max(0.1, d/2.0),
        height=h,
        sections=32,
        transform=tm.transformations.rotation_matrix(math.pi/2, (1,0,0))
    )

def make_model(p: dict) -> tm.Trimesh:
    L = float(p.get("length", 90))
    W = float(p.get("width", 38))
    T = float(p.get("thickness", 8))
    slot = float(p.get("slot_mm", 22))
    screw_d = float(p.get("screw_d_mm", 6.5))
    holes = p.get("holes") or []

    plate = tm.creation.box((L, T, W)); plate.apply_translation((L/2, T/2, W/2))

    # ranura longitudinal centrada
    cut = tm.creation.box((slot, T*2, W*0.4)); cut.apply_translation((L/2, T, W/2))
    body = plate.difference(cut, engine="scad" if tm.interfaces.solid.is_available() else None)

    # puntos guía (3)
    for dx in (-L*0.25, 0.0, L*0.25):
        c = _cyl(screw_d, T*3); c.apply_translation((L/2+dx, T*1.5, W/2))
        body = body.difference(c, engine="scad" if tm.interfaces.solid.is_available() else None)

    # agujeros libres
    for h in holes:
        d = float(h.get("d_mm", 5)); x = float(h.get("x_mm", 0)); z = float(h.get("z_mm", 0))
        c = _cyl(d, T*3); c.apply_translation((x, T*1.5, z))
        body = body.difference(c, engine="scad" if tm.interfaces.solid.is_available() else None)

    return body
