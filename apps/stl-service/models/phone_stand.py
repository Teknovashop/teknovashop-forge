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
    "usb_clear_h": 7.0,
    "wall": 4.0,
    "back_h": 105.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def _difference(base: trimesh.Trimesh, cutter: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        result = trimesh.boolean.difference([base, cutter], engine="manifold")
        if isinstance(result, trimesh.Trimesh):
            return result
    except Exception:
        pass
    return base

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    w = max(55.0, _num(params, "base_w", DEFAULTS["base_w"]))
    d = max(65.0, _num(params, "base_d", DEFAULTS["base_d"]))
    angle = min(80.0, max(45.0, _num(params, "angle_deg", DEFAULTS["angle_deg"])))
    phone_gap = max(7.0, _num(params, "slot_w", DEFAULTS["slot_w"]))
    ledge_d = max(8.0, _num(params, "slot_d", DEFAULTS["slot_d"]))
    usb_clear = max(3.0, _num(params, "usb_clear_h", DEFAULTS["usb_clear_h"]))
    t = max(2.4, _num(params, "wall", DEFAULTS["wall"]))
    back_h = max(70.0, _num(params, "back_h", DEFAULTS["back_h"]))

    base = trimesh.creation.box(extents=(w, d, t))
    base.apply_translation((0.0, 0.0, t / 2))

    back = trimesh.creation.box(extents=(w, t, back_h))
    back.apply_translation((0.0, d * 0.22, back_h / 2 + t))
    tilt = math.radians(90.0 - angle)
    back.apply_transform(
        trimesh.transformations.rotation_matrix(
            tilt, [1, 0, 0], point=[0.0, d * 0.22, t]
        )
    )

    ledge = trimesh.creation.box(extents=(w * 0.82, ledge_d, t))
    ledge.apply_translation((0.0, -d * 0.16, t * 1.5))

    # slot_w representa la holgura/altura útil de retención del teléfono.
    lip_h = phone_gap
    front_lip = trimesh.creation.box(extents=(w * 0.82, t, lip_h))
    front_lip.apply_translation(
        (0.0, -d * 0.16 - ledge_d / 2 + t / 2, t + lip_h / 2)
    )

    # Canal USB-C: su ancho útil cambia con usb_clear_h.
    cutter = trimesh.creation.box(
        extents=(usb_clear, ledge_d * 1.6, t * 4.0)
    )
    cutter.apply_translation((0.0, -d * 0.16, t * 1.5))
    base = _difference(base, cutter)
    ledge = _difference(ledge, cutter)

    mesh = trimesh.util.concatenate([base, ledge, back, front_lip])
    mesh.metadata = {
        "name": "phone_stand",
        "unit": "mm",
        "angle_deg": angle,
        "phone_clearance_mm": phone_gap,
    }
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
