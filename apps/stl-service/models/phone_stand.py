from __future__ import annotations
from typing import Dict, Any
import math
import trimesh

NAME = "phone_stand"
SLUGS = ["phone-stand", "phone-dock", "soporte_movil", "dock_movil"]

DEFAULTS = {
    "base_w": 90.0,
    "base_d": 110.0,
    "angle_deg": 62.0,
    "slot_w": 12.0,
    "slot_d": 16.0,
    "usb_clear_h": 6.0,
    "wall": 4.0,
    "back_h": 105.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    w = max(55.0, _num(params, "base_w", DEFAULTS["base_w"]))
    d = max(65.0, _num(params, "base_d", DEFAULTS["base_d"]))
    angle = min(80.0, max(45.0, _num(params, "angle_deg", DEFAULTS["angle_deg"])))
    phone_gap = max(7.0, _num(params, "slot_w", DEFAULTS["slot_w"]))
    ledge_d = max(8.0, _num(params, "slot_d", DEFAULTS["slot_d"]))
    usb_h = max(3.0, _num(params, "usb_clear_h", DEFAULTS["usb_clear_h"]))
    t = max(2.4, _num(params, "wall", DEFAULTS["wall"]))
    back_h = max(70.0, _num(params, "back_h", DEFAULTS["back_h"]))

    base = trimesh.creation.box(extents=(w, d, t))
    base.apply_translation((0, 0, t / 2))

    # Respaldo inclinado. Partimos de una placa vertical y la inclinamos hacia atrás.
    back = trimesh.creation.box(extents=(w, t, back_h))
    back.apply_translation((0, d * 0.22, back_h / 2 + t))
    tilt = math.radians(90.0 - angle)
    pivot = trimesh.transformations.rotation_matrix(tilt, [1, 0, 0], point=[0, d * 0.22, t])
    back.apply_transform(pivot)

    # Cuna inferior para el teléfono.
    ledge = trimesh.creation.box(extents=(w * 0.82, ledge_d, t))
    ledge.apply_translation((0, -d * 0.16, t * 1.5))

    front_lip = trimesh.creation.box(extents=(w * 0.82, t, max(phone_gap * 0.55, 8.0)))
    front_lip.apply_translation((0, -d * 0.16 - ledge_d / 2 + t / 2, max(phone_gap * 0.55, 8.0) / 2 + t))

    # Canal central para USB-C/cable en base + ledge.
    cutter = trimesh.creation.box(extents=(max(usb_h, 7.0), ledge_d * 1.6, t * 4))
    cutter.apply_translation((0, -d * 0.16, t * 1.5))

    parts = []
    for part in (base, ledge):
        try:
            diff = part.difference(cutter)
            parts.append(diff if isinstance(diff, trimesh.Trimesh) else part)
        except Exception:
            parts.append(part)

    parts.extend([back, front_lip])
    mesh = trimesh.util.concatenate(parts)
    mesh.metadata = {"name": "phone_stand", "unit": "mm", "angle_deg": angle}
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
