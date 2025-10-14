# apps/stl-service/models/utils_geo.py
from __future__ import annotations

from typing import Iterable, Tuple, List
import trimesh

# Alias que faltaba para anotaciones y uso de box/Point/etc.
import shapely.geometry as sg
from shapely.ops import unary_union


def circle(x: float, y: float, d: float, resolution: int = 64) -> sg.Polygon:
    """
    Círculo en (x,y) con diámetro d usando Shapely.
    Se usa para restar agujeros en placas.
    """
    r = max(0.0, float(d or 0.0)) * 0.5
    # evitar radios 0 → buffers degenerados
    if r <= 0:
        r = 0.0001
    return sg.Point(float(x), float(y)).buffer(r, resolution=resolution)


def rounded_rectangle(L: float, W: float, r: float) -> sg.Polygon:
    """
    Rectángulo con esquinas redondeadas mediante buffer.
    r en mm.
    """
    rect = sg.box(-L / 2.0, -W / 2.0, L / 2.0, W / 2.0)
    r = max(0.0, float(r or 0.0))
    if r <= 0:
        return rect
    # buffer positivo y luego negativo para “redondear” esquinas
    return (
        rect.buffer(r, join_style=1, resolution=32)
        .buffer(-r, join_style=1, resolution=32)
    )


def rounded_plate_with_holes(
    L: float,
    W: float,
    T: float,
    holes: Iterable[Tuple[float, float, float]] = (),
    fillet_mm: float = 0.0,
) -> trimesh.Trimesh:
    """
    Placa XY con esquinas redondeadas y agujeros; extrusión +Z.
    (Se mantiene la traducción original si tu pipeline la necesita.)
    """
    poly = rounded_rectangle(L, W, fillet_mm)
    rings: List[sg.Polygon] = []
    for x, y, d in holes or []:
        rings.append(circle(x, y, d))
    interior = unary_union(rings) if rings else None
    if interior:
        poly = poly.difference(interior)

    mesh = trimesh.creation.extrude_polygon(poly, T)
    # OJO: extrude_polygon extruye en Z; esta traslación en Y estaba en tu código.
    # La conservo para no romper dependencias previas.
    mesh.apply_translation((0, T / 2.0, 0))
    return mesh


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
    rings = [circle(x, y, d) for (x, y, d) in holes or []]
    if rings:
        poly = poly.difference(unary_union(rings))

    def path_from_polygon(p: sg.Polygon) -> str:
        # Exterior
        ex = list(p.exterior.coords)
        d = "M " + " L ".join([f"{x:.3f},{-y:.3f}" for x, y in ex]) + " Z"
        # Interiors (si quedaran)
        for hole in p.interiors:
            pts = list(hole.coords)
            d += " M " + " L ".join([f"{x:.3f},{-y:.3f}" for x, y in pts]) + " Z"
        return d

    if isinstance(poly, sg.MultiPolygon):
        d_attr = " ".join(path_from_polygon(geom) for geom in poly.geoms)
    else:
        d_attr = path_from_polygon(poly)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{L:.3f}mm" height="{W:.3f}mm" viewBox="{-L/2:.3f} {-W/2:.3f} {L:.3f} {W:.3f}">'
        f'<path d="{d_attr}" fill="none" stroke="black" stroke-width="{stroke}"/>'
        f"</svg>"
    )
    return svg
