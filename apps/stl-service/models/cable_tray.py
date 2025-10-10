# apps/stl-service/models/cable_tray.py
from typing import Dict, Any, List, Tuple, Iterable
import math
import io

import trimesh
import shapely.geometry as sg
from shapely.ops import unary_union

NAME = "cable_tray"

TYPES = {
    "width": "float",       # separación entre laterales (profundidad de la bandeja)
    "height": "float",      # altura de los laterales
    "length": "float",      # largo
    "thickness": "float",   # espesor chapa
    "fillet": "float",      # radio de esquina en la base
    "holes": "list[tuple[x_mm,y_mm,d_mm]]",  # agujeros en la base (coordenadas 0..L, 0..W)
}

DEFAULTS = {
    "width": 60.0,
    "height": 25.0,
    "length": 180.0,
    "thickness": 3.0,
    "fillet": 0.0,
    "holes": [],
}

# ---------------------- helpers ----------------------

def _parse_holes(holes_in: Iterable) -> List[Tuple[float, float, float]]:
    out: List[Tuple[float, float, float]] = []
    if not holes_in:
        return out
    for h in holes_in:
        try:
            if isinstance(h, dict):
                x = float(h.get("x_mm", 0)); y = float(h.get("y_mm", 0)); d = float(h.get("d_mm", 0))
            else:
                x = float(h[0]); y = float(h[1]); d = float(h[2])
            if d > 0:
                out.append((x, y, d))
        except Exception:
            pass
    return out

def _rounded_rect(L: float, W: float, r: float) -> sg.Polygon:
    r = max(0.0, float(r or 0.0))
    base = sg.box(-L/2.0, -W/2.0, L/2.0, W/2.0)
    if r <= 0:
        return base
    # buffer-trick para redondear esquinas con buena calidad
    return base.buffer(r, join_style=1, resolution=64).buffer(-r, join_style=1, resolution=64)

# ---------------------- modelo 3D (U real) ----------------------

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(params.get("length", params.get("length_mm", DEFAULTS["length"])))
    W = float(params.get("width", params.get("width_mm", DEFAULTS["width"])))
    H = float(params.get("height", params.get("height_mm", DEFAULTS["height"])))
    T = float(params.get("thickness", params.get("thickness_mm", DEFAULTS["thickness"])))
    F = float(params.get("fillet", params.get("fillet_mm", DEFAULTS["fillet"])))
    holes = _parse_holes(params.get("holes", []))

    # --- Base con fillet
    rect = _rounded_rect(L, W, F)
    base = trimesh.creation.extrude_polygon(rect, T)
    base.apply_translation((0, 0, T * 0.5))  # Z=0 .. Z=T

    # --- Laterales (placas verticales)
    left = trimesh.creation.box(extents=(L, T, H))
    left.apply_translation((0, -(W/2 - T/2), T + H/2))

    right = trimesh.creation.box(extents=(L, T, H))
    right.apply_translation((0,  (W/2 - T/2), T + H/2))

    tray = trimesh.util.concatenate([base, left, right])

    # --- Agujeros en la base (coordenadas 0..L, 0..W, diámetro d)
    cutters = []
    for (x, y, d) in holes:
        if d <= 0: 
            continue
        cx = x - L*0.5
        cy = y - W*0.5
        drill = trimesh.creation.cylinder(radius=d*0.5, height=max(T*2.0, 6.0), sections=64)
        drill.apply_translation((cx, cy, T*0.5))
        cutters.append(drill)
    if cutters:
        try:
            from trimesh import boolean
            tray = boolean.difference([tray] + cutters, engine=None)
            if isinstance(tray, trimesh.Scene):
                tray = tray.dump(concatenate=True)
        except Exception:
            pass

    return tray if isinstance(tray, trimesh.Trimesh) else trimesh.util.concatenate([base, left, right])

# ---------------------- SVG (contorno base + agujeros) ----------------------

def make_svg(params: Dict[str, Any], holes_in: Iterable) -> str:
    """
    Devuelve un SVG 2D (mm) de la BASE: contorno con fillet + taladros.
    Se usa para corte láser.
    """
    L = float(params.get("length", params.get("length_mm", DEFAULTS["length"])))
    W = float(params.get("width", params.get("width_mm", DEFAULTS["width"])))
    T = float(params.get("thickness", params.get("thickness_mm", DEFAULTS["thickness"])))
    F = float(params.get("fillet", params.get("fillet_mm", DEFAULTS["fillet"])))

    holes = _parse_holes(holes_in)

    # Usamos viewBox en mm. Origen en el centro (0,0) para facilitar.
    rect = _rounded_rect(L, W, F)
    path = rect.svg()  # path 'd' del contorno

    circles = []
    for (x, y, d) in holes:
        if d <= 0: 
            continue
        # trasladamos a un sistema centrado: (0..L,0..W) -> (-L/2.., -W/2..)
        cx = x - L*0.5
        cy = -(y - W*0.5)  # invertimos Y para SVG
        circles.append(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{d*0.5:.3f}" />')

    # SVG con unidades en mm y trazo mínimo (sin relleno)
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{L}mm" height="{W}mm" viewBox="{-(L/2):.3f} {-(W/2):.3f} {L:.3f} {W:.3f}">
  <g fill="none" stroke="black" stroke-width="0.2">
    <path d="{path}" />
    {''.join(circles)}
  </g>
</svg>
'''
    return svg
