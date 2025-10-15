# apps/stl-service/models/__init__.py
from typing import Dict, Any
import trimesh
from trimesh.creation import box


def mm(v, default):
    try:
        x = float(v)
        return x if x > 0 else default
    except Exception:
        return default


def make_plate(p: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Placa rectangular básica: length x width x thickness, apoyada sobre Z=0.
    El resto (agujeros, arrays, redondeos) se aplica después en app.py.
    """
    L = mm(p.get("length_mm") or p.get("length"), 120.0)
    W = mm(p.get("width_mm") or p.get("width"), 100.0)
    T = mm(p.get("thickness_mm") or p.get("wall") or p.get("thickness") or 3.0, 3.0)
    mesh = box(extents=(L, W, T))
    # Coloca la placa con la base en Z=0 (más cómodo para el visor)
    mesh.apply_translation((L * 0.5, W * 0.5, T * 0.5))
    return mesh


# Si tienes generadores específicos (ej. cable_tray con paredes),
# puedes sustituir make_plate por tus funciones reales más adelante.
REGISTRY: Dict[str, Dict[str, Any]] = {
    # 1
    "cable_tray": {
        "defaults": {"length_mm": 120, "width_mm": 100, "thickness_mm": 3},
        "make": make_plate,
    },
    # 2
    "vesa_adapter": {
        "defaults": {"length_mm": 120, "width_mm": 120, "thickness_mm": 3},
        "make": make_plate,
    },
    # 3
    "router_mount": {
        "defaults": {"length_mm": 120, "width_mm": 80, "thickness_mm": 4},
        "make": make_plate,
    },
    # 4
    "cable_clip": {
        "defaults": {"length_mm": 40, "width_mm": 20, "thickness_mm": 3},
        "make": make_plate,
    },
    # 5
    "headset_stand": {
        "defaults": {"length_mm": 150, "width_mm": 60, "thickness_mm": 5},
        "make": make_plate,
    },
    # 6
    "phone_dock": {
        "defaults": {"length_mm": 100, "width_mm": 60, "thickness_mm": 8},
        "make": make_plate,
    },
    # 7
    "tablet_stand": {
        "defaults": {"length_mm": 150, "width_mm": 100, "thickness_mm": 6},
        "make": make_plate,
    },
    # 8
    "ssd_holder": {
        "defaults": {"length_mm": 100, "width_mm": 70, "thickness_mm": 3},
        "make": make_plate,
    },
    # 9
    "raspi_case": {
        "defaults": {"length_mm": 95, "width_mm": 65, "thickness_mm": 3},
        "make": make_plate,
    },
    # 10
    "go_pro_mount": {
        "defaults": {"length_mm": 60, "width_mm": 40, "thickness_mm": 5},
        "make": make_plate,
    },
    # 11
    "wall_hook": {
        "defaults": {"length_mm": 80, "width_mm": 40, "thickness_mm": 6},
        "make": make_plate,
    },
    # 12
    "monitor_stand": {
        "defaults": {"length_mm": 200, "width_mm": 120, "thickness_mm": 8},
        "make": make_plate,
    },
    # 13
    "laptop_stand": {
        "defaults": {"length_mm": 220, "width_mm": 120, "thickness_mm": 8},
        "make": make_plate,
    },
    # 14
    "mic_arm_clip": {
        "defaults": {"length_mm": 60, "width_mm": 40, "thickness_mm": 5},
        "make": make_plate,
    },
    # 15
    "camera_plate": {
        "defaults": {"length_mm": 120, "width_mm": 100, "thickness_mm": 4},
        "make": make_plate,
    },
    # 16
    "hub_holder": {
        "defaults": {"length_mm": 120, "width_mm": 60, "thickness_mm": 4},
        "make": make_plate,
    },
}
