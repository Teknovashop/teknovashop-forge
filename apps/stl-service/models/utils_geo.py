# apps/stl-service/models/utils_geo.py
from math import pi
from typing import Iterable, List, Tuple

import numpy as np
import shapely.geometry as sg
import shapely.affinity as sa
from shapely.ops import unary_union
import trimesh


def circle(x: float, y: float, d: float) -> sg.Polygon:
    r = d / 2.0
    return sg.Point(x, y).buffer(r, resolution=64)


def slot(x: float, y: float, length: float, d: float, angle_deg: float = 0.0) -> sg.Polygon:
    """
    "cápsula": rectángulo + semicircunferencias.
    length = longitud total (de centro a centro de los semicírculos).
    """
    r = d / 2.0
    rect = sg.box(x - length / 2.0, y - r, x + length / 2.0, y + r)
    caps = circle(x - length / 2.0, y, d).union(circle(x + length / 2.0, y, d))
    poly = rect.union(caps)
    if angle_deg:
        poly = sa.rotate(poly, angle_deg, origin=(x, y))
    return poly


def plate_with_holes(L: float, W: float, T: float, holes: Iterable[Tuple[float, float, float]] = ()) -> trimesh.Trimesh:
    """
    Genera placa (XY) con agujeros circulares (x,z,d). Se extruye en +Y (espesor T).
    Origen en (0,0,0). Placa centrada en XZ y apoyada en Y=0.
    """
    outer = sg.box(-L / 2.0, -W / 2.0, L / 2.0, W / 2.0)
    rings: List[sg.Polygon] = []
    for x, z, d in holes:
        rings.append(circle(x, z, d))
    interior = unary_union(rings) if rings else None
    if interior:
        poly = outer.difference(interior)
    else:
        poly = outer
    mesh = trimesh.creation.extrude_polygon(poly, T)
    # desplazar para apoyar en Y=0
    mesh.apply_translation((0, T / 2.0, 0))
    return mesh


def rectangle_plate(L: float, H: float, T: float, holes: Iterable[Tuple[float, float, float]] = ()) -> trimesh.Trimesh:
    """
    Placa vertical (X por Y = altura) con agujeros (x,y,d). Se coloca centrada en X y Z=0.
    """
    outer = sg.box(-L / 2.0, 0.0, L / 2.0, H)
    rings: List[sg.Polygon] = []
    for x, y, d in holes:
        rings.append(circle(x, y, d))
    interior = unary_union(rings) if rings else None
    if interior:
        poly = outer.difference(interior)
    else:
        poly = outer
    mesh = trimesh.creation.extrude_polygon(poly, T)
    mesh.apply_translation((0, T / 2.0, 0))
    return mesh


def concatenate(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    meshes = [m for m in meshes if m is not None]
    return trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
