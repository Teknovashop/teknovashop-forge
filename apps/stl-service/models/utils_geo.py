# apps/stl-service/models/utils_geo.py
from __future__ import annotations

from typing import Iterable, Tuple, List, Optional
import trimesh

# Shapely
import shapely.geometry as sg
import shapely.affinity as sa
from shapely.ops import unary_union


def circle(x: float, y: float, d: float, resolution: int = 64) -> sg.Polygon:
    """
    Círculo en (x,y) con diámetro d usando Shapely.
    Se usa para restar agujeros en placas.
    """
    r = max(0.0, float(d or 0.0)) * 0.5
    # Evitar radios 0 → buffers degenerados
    if r <= 0:
        r = 0.0001
    return sg.Point(float(x), float(y)).buffer(r, resolution=resolution)


def rounded_rectangle(L: float, W: float, r: float) -> sg.Polygon:
    """
    Rectángulo centrado en (0,0) con esquinas redondeadas mediante buffer.
    L = size X, W = size Y, r en mm.
    """
    rect = sg.box(-L / 2.0, -W / 2.0, L / 2.0, W / 2.0)
    r = max(0.0, float(r or 0.0))
    if r <= 0:
        return rect
    # Buffer positivo y luego negativo para redondear esquinas
    return (
        rect.buffer(r, join_style=1, resolution=32)
        .buffer(-r, join_style=1, resolution=32)
    )


def slot(
    x: float,
    y: float,
    w: float,
    h: float,
    r: Optional[float] = None,
    angle_deg: float = 0.0,
    resolution: int = 64,
) -> sg.Polygon:
    """
    Ranura (capsule/oblong) centrada en (x,y).
    - Si no se indica r, se toma r = min(w,h)/2 (estadio clásico).
    - angle_deg rota la ranura (0 = eje horizontal).
    Devuelve un *Polygon* de Shapely.
    """
    w = float(w); h = float(h)
    if w <= 0 or h <= 0:
        # Fallback a un punto casi nulo para no romper booleanas
        return sg.Point(x, y).buffer(1e-4)
    r = float(r) if (r is not None) else min(w, h) * 0.5
    r = max(0.0, r)

    if r == 0:
        shape = sg.box(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)
    else:
        # Construcción por unión: rectángulo + dos semicircunferencias en extremos
        if w >= h:
            # Estadio horizontal: “cuerpo” alargado en X
            rect_len = max(w - 2 * r, 0.0)
            rect = sg.box(-rect_len / 2.0, -h / 2.0, rect_len / 2.0, h / 2.0)
            capL = sg.Point(-rect_len / 2.0, 0.0).buffer(r, resolution=resolution)
            capR = sg.Point(+rect_len / 2.0, 0.0).buffer(r, resolution=resolution)
            shape = unary_union([rect, capL, capR])
        else:
            # Estadio vertical: “cuerpo” alargado en Y
            rect_len = max(h - 2 * r, 0.0)
            rect = sg.box(-w / 2.0, -rect_len / 2.0, w / 2.0, rect_len / 2.0)
            capB = sg.Point(0.0, -rect_len / 2.0).buffer(r, resolution=resolution)
            capT = sg.Point(0.0, +rect_len / 2.0).buffer(r, resolution=resolution)
            shape = unary_union([rect, capB, capT])

    # Rotar y trasladar a (x,y)
    if angle_deg:
        shape = sa.rotate(shape, angle_deg, origin=(0, 0), use_radians=False)
    shape = sa.translate(shape, xoff=float(x), yoff=float(y))
    return shape


def rounded_plate_with_holes(
    L: float,
    W: float,
    T: float,
    holes: Iterable[Tuple[float, float, float]] = (),
    fillet_mm: float = 0.0,
) -> trimesh.Trimesh:
    """
    Placa XY con esquinas redondeadas y agujeros; extrusión +Z.
    """
    poly = rounded_rectangle(L, W, fillet_mm)

    rings: List[sg.Polygon] = []
    for xh, yh, dh in holes or []:
        rings.append(circle(xh, yh, dh))
    interior = unary_union(rings) if rings else None
    if interior:
        poly = poly.difference(interior)

    mesh = trimesh.creation.extrude_polygon(poly, T)
    # Conservamos tu traslación para no romper dependencias
    mesh.apply_translation((0, T / 2.0, 0))
    return mesh


# ✅ Alias por compatibilidad histórica con modelos que importan este nombre:
def plate_with_holes(
    L: float,
    W: float,
    T: float,
    holes: Iterable[Tuple[float, float, float]] = (),
    fillet_mm: float = 0.0,
) -> trimesh.Trimesh:
    return rounded_plate_with_holes(L, W, T, holes=holes, fillet_mm=fillet_mm)


def rectangle_plate(L: float, W: float, T: float) -> trimesh.Trimesh:
    """Placa rectangular centrada (sin redondeo), extruida en +Z y desplazada T/2 en Y para compatibilidad."""
    poly = sg.box(-L/2.0, -W/2.0, L/2.0, W/2.0)
    mesh = trimesh.creation.extrude_polygon(poly, T)
    mesh.apply_translation((0, T/2.0, 0))
    return mesh


def concatenate(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Wrapper de compatibilidad – algunos modelos importan esto desde utils_geo."""
    meshes = [m for m in meshes if isinstance(m, trimesh.Trimesh)]
    if not meshes:
        return trimesh.Trimesh()
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.util.concatenate(meshes)


def svg_plate(
    L: float,
    W: float,
    holes: Iterable[Tuple[float, float, float]] = (),
    fillet_mm: float = 0.0,
    stroke: float = 1.0,
) -> str:
    """
    Devuelve un SVG simple (mm) con contorno exterior y agujeros circulares.
    Pensado para láser/plotter. Sin relleno, solo trazo.
    """
    poly = rounded_rectangle(L, W, fillet_mm)

    # restamos los agujeros al contorno
    rings = [circle(xh, yh, dh) for (xh, yh, dh) in holes or []]
    if rings:
        poly = poly.difference(unary_union(rings))

    def path_from_polygon(p: sg.Polygon) -> str:
        # Exterior
        ex = list(p.exterior.coords)
        d_attr = "M " + " L ".join([f"{x:.3f},{-y:.3f}" for x, y in ex]) + " Z"
        # Interiors (si quedaran)
        for hole in p.interiors:
            pts = list(hole.coords)
            d_attr += " M " + " L ".join([f"{x:.3f},{-y:.3f}" for x, y in pts]) + " Z"
        return d_attr

    if isinstance(poly, sg.MultiPolygon):
        d_all = " ".join(path_from_polygon(geom) for geom in poly.geoms)
    else:
        d_all = path_from_polygon(poly)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{L:.3f}mm" height="{W:.3f}mm" viewBox="{-L/2:.3f} {-W/2:.3f} {L:.3f} {W:.3f}">'
        f'<path d="{d_all}" fill="none" stroke="black" stroke-width="{stroke}"/>'
        f"</svg>"
    )
    return svg
