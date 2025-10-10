# apps/stl-service/models/cable_tray.py
from typing import Dict, Any, List, Tuple
import trimesh
import shapely.geometry as sg
from shapely.ops import unary_union

from ._helpers import parse_holes
from .utils_geo import rectangle_plate, plate_with_holes, concatenate  # se mantienen por compatibilidad

NAME = "cable_tray"

TYPES = {
    "width": "float",       # separación entre laterales (profundidad de la bandeja)
    "height": "float",      # altura de los laterales
    "length": "float",      # largo
    "thickness": "float",   # espesor chapa
    "ventilated": "bool",   # si True, ranuras en la base
    "holes": "list[tuple[float, float, float], tuple[float, float, float]]",  # agujeros en lateral izq/der (x,y,d)
    # soporte opcional ya presente en Params del API:
    "fillet_mm": "float",   # radio de esquinas de la base (opcional)
}

DEFAULTS = {
    "width": 60.0,
    "height": 25.0,
    "length": 180.0,
    "thickness": 3.0,
    "ventilated": True,
    "holes": [],      # (x,y,d) relativo al lateral (placa vertical)
    "fillet_mm": 0.0  # 🔹 nuevo (no rompe)
}

# ----------------- helpers locales (no requieren tocar utils_geo) -----------------

def _circle(x: float, y: float, d: float) -> sg.Polygon:
    r = max(0.05, float(d) * 0.5)
    return sg.Point(float(x), float(y)).buffer(r, resolution=48)

def _rounded_rectangle(L: float, W: float, r: float) -> sg.Polygon:
    rect = sg.box(-L/2.0, -W/2.0, L/2.0, W/2.0)
    r = max(0.0, float(r or 0.0))
    if r <= 0.0:
        return rect
    # suavizado de esquinas con buffer positivo y negativo
    return rect.buffer(r, join_style=1, resolution=32).buffer(-r, join_style=1, resolution=32)

def _rounded_plate_with_holes(
    L: float, W: float, T: float,
    holes: List[Tuple[float, float, float]],
    fillet_mm: float
) -> trimesh.Trimesh:
    poly = _rounded_rectangle(L, W, fillet_mm)
    if holes:
        cuts = unary_union([_circle(x, y, d) for x, y, d in holes])
        poly = poly.difference(cuts)
    mesh = trimesh.creation.extrude_polygon(poly, T)
    mesh.apply_translation((0, 0, T * 0.5))
    return mesh

def make_svg(params: Dict[str, Any], holes_any: List[Any]) -> str:
    """
    Devuelve un SVG (mm) del contorno de la base con agujeros.
    Se usa desde /generate si outputs contiene "svg".
    """
    W = float(params.get("width", DEFAULTS["width"]))
    L = float(params.get("length", DEFAULTS["length"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    F = float(params.get("fillet_mm", DEFAULTS["fillet_mm"]))
    holes = parse_holes(holes_any or [])

    # Construye polígono con redondeo y agujeros
    poly = _rounded_rectangle(L, W, F)
    if holes:
        cuts = unary_union([_circle(x, y, d) for x, y, d in holes])
        poly = poly.difference(cuts)

    def path_from_polygon(p: sg.Polygon) -> str:
        ex = list(p.exterior.coords)
        d = "M " + " L ".join([f"{x:.3f},{-y:.3f}" for x, y in ex]) + " Z"
        for hole in p.interiors:
            pts = list(hole.coords)
            d += " M " + " L ".join([f"{x:.3f},{-y:.3f}" for x, y in pts]) + " Z"
        return d

    if isinstance(poly, sg.MultiPolygon):
        d_attr = " ".join(path_from_polygon(g) for g in poly.geoms)
    else:
        d_attr = path_from_polygon(poly)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{L:.3f}mm" height="{W:.3f}mm" viewBox="{-L/2:.3f} {-W/2:.3f} {L:.3f} {W:.3f}">'
        f'<path d="{d_attr}" fill="none" stroke="black" stroke-width="1"/>'
        f"</svg>"
    )
    return svg

# -------------------------------------------------------------------------------

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    W = float(params.get("width", DEFAULTS["width"]))
    H = float(params.get("height", DEFAULTS["height"]))
    L = float(params.get("length", DEFAULTS["length"]))
    T = float(params.get("thickness", DEFAULTS["thickness"]))
    F = float(params.get("fillet_mm", DEFAULTS["fillet_mm"]))
    holes = parse_holes(params.get("holes", []))
    ventilated = bool(params.get("ventilated", DEFAULTS["ventilated"]))

    # Dos laterales (placas verticales)
    left = rectangle_plate(L, H, T, holes)   # lateral izquierdo
    right = rectangle_plate(L, H, T, holes)  # reutilizamos mismos agujeros
    right.apply_translation((0, 0, W))       # separarlo por el ancho

    # Base: placa horizontal. Si ventilated: “ventanas” circulares simples
    base_holes: List[Tuple[float, float, float]] = []
    if ventilated:
        n = max(1, int(L // 30))
        step = L / (n + 1)
        x0 = -L / 2.0 + step
        for i in range(n):
            base_holes.append((x0 + i * step, 0.0, min(8.0, W * 0.5)))

    # 🔹 NUEVO: base con esquinas redondeadas (si F=0, es equivalente a antes)
    base = _rounded_plate_with_holes(L, W, T, base_holes, F)
    base.apply_translation((0, 0, W / 2.0))  # centrar en Z entre los laterales

    # Ensamblado
    tray = concatenate([left, right, base])
    return tray
