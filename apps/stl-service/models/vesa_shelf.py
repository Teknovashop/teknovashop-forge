# apps/stl-service/models/vesa_shelf.py
# Estante VESA para mini-PC/NUC con quick-release básico (opcional)
# Implementado con trimesh (sin cadquery) para no añadir dependencias.

from __future__ import annotations
import math
from typing import Dict, Any, Tuple, List

import numpy as np
import trimesh


DEFAULTS: Dict[str, Any] = {
    "vesa": 100,            # 75 / 100 / 200
    "thickness": 4.0,       # grueso placa y estante
    "shelf_width": 180.0,   # ancho útil del estante
    "shelf_depth": 120.0,   # fondo (sale hacia -Y en el STL)
    "lip_height": 15.0,     # pestaña frontal anti-caída
    "rib_count": 3,         # nº de refuerzos verticales
    "hole_d": 5.0,          # taladros VESA
    "qr_enabled": True,     # quick-release muy simple (ranura)
    "qr_slot_w": 18.0,
    "qr_slot_h": 6.0,
    "qr_offset_y": 12.0,
}

def _box(size_xyz: Tuple[float, float, float]) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=size_xyz)

def _cyl(radius: float, height: float, sections: int = 64) -> trimesh.Trimesh:
    return trimesh.creation.cylinder(radius=radius, height=height, sections=sections)

def _translate(m: trimesh.Trimesh, x=0.0, y=0.0, z=0.0) -> trimesh.Trimesh:
    m = m.copy()
    m.apply_translation([x, y, z])
    return m

def _union(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    meshes = [m for m in meshes if m is not None]
    if not meshes:
        return None
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.boolean.union(meshes, engine="scad")  # usa OpenSCAD si está disponible; si no, cuadrará con cork/igl si presentes

def _difference(a: trimesh.Trimesh, cutters: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    cutters = [c for c in cutters if c is not None]
    if not cutters:
        return a
    return trimesh.boolean.difference([a] + cutters, engine="scad")

def _vesa_hole_positions(pitch: float) -> List[Tuple[float, float]]:
    half = pitch / 2.0
    return [(-half, -half), (half, -half), (-half, half), (half, half)]

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Construye el estante VESA.
    Convenciones:
      - Unidades: mm
      - Ejes: X (ancho), Y (fondo; el estante se extiende hacia -Y), Z (alto)
      - El origen queda en la esquina inferior-izquierda de la placa trasera (tras centrado global).
    """
    p = DEFAULTS.copy()
    if params:
        p.update(params)

    vesa = float(p["vesa"])
    t = float(p["thickness"])
    w = float(p["shelf_width"])
    d = float(p["shelf_depth"])
    lip_h = float(p["lip_height"])
    ribs = int(p["rib_count"])
    hole_d = float(p["hole_d"])

    # --- 1) Placa trasera (vesa + margen)
    margin = 40.0
    back_w = vesa + margin
    back_h = vesa + margin
    back = _box((back_w, t, back_h))
    # por defecto el box se centra en (0,0,0); lo llevamos a que asiente sobre Z=0 y centrado en X
    back = _translate(back, 0, 0, back_h / 2.0)

    # --- 2) Taladros VESA
    holes = []
    for (hx, hz) in _vesa_hole_positions(vesa):
        cyl = _cyl(radius=hole_d / 2.0, height=t * 2.0)
        cyl = _translate(cyl, hx, 0, hz + back_h / 2.0)  # centra en Z de la placa
        holes.append(cyl)
    back = _difference(back, holes)

    # --- 3) Estante (sale hacia -Y)
    shelf = _box((w, d, t))
    # Alinear el canto trasero del estante con la parte inferior de la placa
    # Colocamos el estante centrado en X, con su borde trasero tocando la placa (en Y = -t/2)
    shelf = _translate(shelf, 0, -(d / 2.0 + t / 2.0), t / 2.0)

    # --- 4) Labio frontal
    lip = _box((w, t, lip_h))
    # Colocar al frente del estante: y = -(d + t)/2  y elevar en Z
    lip = _translate(lip, 0, -(d + t) / 2.0, t / 2.0 + lip_h / 2.0)

    # --- 5) Refuerzos (ribs) como tabiques perpendiculares al estante
    ribs_meshes: List[trimesh.Trimesh] = []
    if ribs > 0:
        step = w / (ribs + 1)
        xs = [(-w / 2.0 + step * (i + 1)) for i in range(ribs)]
        for x in xs:
            rib = _box((t, d, t))  # tabique fino del grosor t
            rib = _translate(rib, x, -(d / 2.0 + t / 2.0), t / 2.0)
            ribs_meshes.append(rib)

    model = _union([back, shelf, lip] + ribs_meshes)

    # --- 6) Quick-release (ranura rectangular en la placa)
    if bool(p["qr_enabled"]):
        slot_w = float(p["qr_slot_w"])
        slot_h = float(p["qr_slot_h"])
        qr_off_y = float(p["qr_offset_y"])

        slot = _box((slot_w, t * 2.0, slot_h))
        # Centro de la placa está en (0, 0, back_h/2). Llevamos la ranura un poco arriba (+qr_off_y).
        slot = _translate(slot, 0, 0, back_h / 2.0 + qr_off_y)
        model = _difference(model, [slot])

    # Normalizar orientación: que el “suelo” quede en Z=0
    # (ya construido así). Opcionalmente, trasladar para que el centro geométrico sea (0,0,0):
    model = model.copy()
    model.metadata = {"name": "vesa_shelf", "unit": "mm"}
    return model
