# apps/stl-service/models/cable_tray.py
import math
import trimesh
import shapely.geometry as sg
from trimesh.transformations import translation_matrix as T

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def make_model(p: dict) -> trimesh.Trimesh:
    """
    Canal en U (X=length, Y=height, Z=width) con base perforable.
    Admite 'holes': lista de {x_mm, z_mm, d_mm}.
    """
    L   = _safe_float(p.get("length",    p.get("length_mm", 180)))
    H   = _safe_float(p.get("height",    p.get("height_mm", 25)))
    W   = _safe_float(p.get("width",     p.get("width_mm",  60)))
    TCK = _safe_float(p.get("thickness", p.get("thickness_mm", 3)))
    ventilated = bool(p.get("ventilated", True))

    holes = p.get("holes") or []
    # -- paredes laterales
    side1 = trimesh.creation.box(extents=[L, H, TCK]); side1.apply_transform(T([0, 0, -W/2 + TCK/2]))
    side2 = trimesh.creation.box(extents=[L, H, TCK]); side2.apply_transform(T([0, 0,  W/2 - TCK/2]))

    parts = [side1, side2]

    # -- base (dos caminos: con agujeros -> extrusión de polígono; sin agujeros -> box)
    if holes:
        # polígono 2D en plano XZ (centro en 0,0)
        halfL = L * 0.5
        halfW = W * 0.5
        outer = sg.Polygon([(-halfL, -halfW), ( halfL, -halfW),
                            ( halfL,  halfW), (-halfL,  halfW)])

        # círculos como agujeros
        holes_polys = []
        for h in holes:
            x = _safe_float(h.get("x_mm", h.get("x")))
            z = _safe_float(h.get("z_mm", h.get("z")))
            d = max(0.1, _safe_float(h.get("d_mm", h.get("diameter_mm", h.get("d", 5.0)))))
            r = d * 0.5
            holes_polys.append(sg.Point(x, z).buffer(r, resolution=32))

        poly = sg.Polygon(outer.exterior.coords,
                          holes=[hp.exterior.coords for hp in holes_polys] if holes_polys else None)

        # extruir hacia +Y con el espesor de la base
        base = trimesh.creation.extrude_polygon(poly, height=TCK)
        # colocar la base a la altura correcta (la base original estaba centrada y “baja” en Y)
        base.apply_transform(T([0, -H/2 + TCK/2, 0]))
    else:
        base = trimesh.creation.box(extents=[L, TCK, W])
        base.apply_transform(T([0, -H/2 + TCK/2, 0]))

    parts.append(base)

    # -- listones de ventilación superficiales (decorativos; no CSG)
    if ventilated:
        n = max(3, int(L // 40))
        gap = L / (n + 1)
        rib_w = max(2.0, min(6.0, W * 0.08))
        for i in range(1, n + 1):
            rib = trimesh.creation.box(extents=[rib_w, TCK * 1.05, W - 2 * TCK])
            rib.apply_transform(T([-L/2 + i * gap, -H/2 + TCK/2 + 0.01, 0]))
            parts.append(rib)

    return trimesh.util.concatenate(parts)
