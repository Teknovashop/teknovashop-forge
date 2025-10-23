# apps/stl-service/models/camera_plate.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import trimesh

NAME = "camera_plate"
SLUGS = ["camera-plate", "qr-plate"]

DEFAULTS: Dict[str, float] = {
    "width": 45.0,
    "depth": 50.0,
    "thickness": 6.0,
    "screw_d": 6.35,   # 1/4"-20 ~ 6.35mm
    "slot_len": 18.0,  # largo de la ranura longitudinal
    "slot_w": 6.0,     # ancho ranura (ligeramente > tornillo)
}

TYPES = {
    "width": "float",
    "depth": "float",
    "thickness": "float",
    "screw_d": "float",
    "slot_len": "float",
    "slot_w": "float",
}

def _num(p: Dict[str, Any], k: str, fb: float) -> float:
    try:
        return float(str(p.get(k, fb)).replace(",", "."))
    except Exception:
        return fb

def _slot_cutter(slot_len: float, slot_w: float, height: float) -> trimesh.Trimesh:
    """
    Crea un "cutter" tipo cápsula (dos cilindros + prisma) para generar una ranura.
    Orientado a lo largo del eje Y.
    """
    r = slot_w * 0.5
    h = height
    core = trimesh.creation.box(extents=(slot_w, slot_len, h))

    cap = trimesh.creation.cylinder(radius=r, height=h, sections=64)
    cap1 = cap.copy(); cap1.apply_translation((0.0,  slot_len * 0.5, 0.0))
    cap2 = cap.copy(); cap2.apply_translation((0.0, -slot_len * 0.5, 0.0))

    return trimesh.util.concatenate([core, cap1, cap2])

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    W  = _num(params, "width",      DEFAULTS["width"])
    D  = _num(params, "depth",      DEFAULTS["depth"])
    T  = _num(params, "thickness",  DEFAULTS["thickness"])
    d0 = _num(params, "screw_d",    DEFAULTS["screw_d"])
    Ls = _num(params, "slot_len",   DEFAULTS["slot_len"])
    Ws = _num(params, "slot_w",     DEFAULTS["slot_w"])

    # Placa base centrada en el origen
    base = trimesh.creation.box(extents=(W, D, T))

    cutters: List[trimesh.Trimesh] = []

    # Agujero central (1/4"-20)
    hole = trimesh.creation.cylinder(radius=d0 * 0.5, height=T * 1.4, sections=96)
    cutters.append(hole)

    # Ranura longitudinal paralela al eje Y
    slot = _slot_cutter(Ls, Ws, T * 1.4)
    # desplaza la ranura hacia un lado para dejar el agujero central
    slot.apply_translation((W * 0.18, 0.0, 0.0))
    cutters.append(slot)

    cutter = trimesh.util.concatenate(cutters)
    # Boolean – usa OpenSCAD si está, si no el motor que tenga trimesh
    engine = "scad" if getattr(trimesh.interfaces.scad, "exists", False) else None
    plate = base.difference(cutter, engine=engine)
    return plate if isinstance(plate, trimesh.Trimesh) else base

# compat
def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "SLUGS", "TYPES", "DEFAULTS", "make", "make_model", "BUILD"]
