# apps/stl-service/models/__init__.py
from typing import Dict, Any, Callable, List
import trimesh
from trimesh.creation import box


def _plate(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(params.get("length_mm", 120.0))
    W = float(params.get("width_mm", 100.0))
    T = float(params.get("thickness_mm", 3.0))
    # placa plana apoyada en Z=0
    m = box((L, W, T))
    m.apply_translation((L * 0.5, W * 0.5, T * 0.5))
    return m


def _block(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(params.get("length_mm", 80.0))
    W = float(params.get("width_mm", 40.0))
    H = float(params.get("height_mm", 30.0))
    m = box((L, W, H))
    m.apply_translation((L * 0.5, W * 0.5, H * 0.5))
    return m


# Ejemplo de uno “real”: si tienes un módulo especifico, impórtalo y úsalo aquí
def _vesa_adapter(params: Dict[str, Any]) -> trimesh.Trimesh:
    # Hasta que metas tu implementación detallada, usa placa base
    return _plate(params)


# REGISTRY
# - key: slug que llega desde el frontend (ForgeForm MODEL_OPTIONS)
# - aliases: otros nombres que quieras aceptar (compatibilidad)
# - defaults: valores por defecto para ese modelo
REGISTRY: Dict[str, Dict[str, Any]] = {
    "cable_tray": {
        "make": _plate,
        "defaults": {"thickness_mm": 3.0},
        "aliases": [],
    },
    "vesa_adapter": {
        "make": _vesa_adapter,
        "defaults": {"length_mm": 120.0, "width_mm": 120.0, "thickness_mm": 3.0},
        "aliases": ["vesa", "vesa_plate"],
    },
    "router_mount": {
        "make": _block,
        "defaults": {"length_mm": 120.0, "width_mm": 60.0, "height_mm": 60.0},
        "aliases": ["router_mount_l"],
    },
    "cable_clip": {
        "make": _block,
        "defaults": {"length_mm": 30.0, "width_mm": 15.0, "height_mm": 15.0},
        "aliases": [],
    },
    "headset_stand": {
        "make": _block,
        "defaults": {"length_mm": 100.0, "width_mm": 50.0, "height_mm": 180.0},
        "aliases": [],
    },
    "phone_dock": {
        "make": _block,
        "defaults": {"length_mm": 90.0, "width_mm": 70.0, "height_mm": 30.0},
        "aliases": ["phone_dock_usbc", "phone_dock_usb_c"],
    },
    "tablet_stand": {
        "make": _block,
        "defaults": {"length_mm": 150.0, "width_mm": 120.0, "height_mm": 40.0},
        "aliases": [],
    },
    "ssd_holder": {
        "make": _plate,
        "defaults": {"length_mm": 100.0, "width_mm": 70.0, "thickness_mm": 4.0},
        "aliases": ["ssd_2_5"],
    },
    "raspi_case": {
        "make": _block,
        "defaults": {"length_mm": 95.0, "width_mm": 65.0, "height_mm": 30.0},
        "aliases": ["raspberry_pi_case", "raspberry_case"],
    },
    "go_pro_mount": {
        "make": _block,
        "defaults": {"length_mm": 45.0, "width_mm": 30.0, "height_mm": 30.0},
        "aliases": ["gopro_mount"],
    },
    "wall_hook": {
        "make": _block,
        "defaults": {"length_mm": 60.0, "width_mm": 20.0, "height_mm": 40.0},
        "aliases": [],
    },
    "monitor_stand": {
        "make": _block,
        "defaults": {"length_mm": 300.0, "width_mm": 200.0, "height_mm": 40.0},
        "aliases": [],
    },
    "laptop_stand": {
        "make": _block,
        "defaults": {"length_mm": 270.0, "width_mm": 220.0, "height_mm": 40.0},
        "aliases": [],
    },
    "mic_arm_clip": {
        "make": _block,
        "defaults": {"length_mm": 40.0, "width_mm": 20.0, "height_mm": 25.0},
        "aliases": ["mic_clip"],
    },
    "camera_plate": {
        "make": _plate,
        "defaults": {"length_mm": 80.0, "width_mm": 50.0, "thickness_mm": 5.0},
        "aliases": ["camera_plate_1_4"],
    },
    "hub_holder": {
        "make": _block,
        "defaults": {"length_mm": 120.0, "width_mm": 40.0, "height_mm": 25.0},
        "aliases": ["usb_hub_holder"],
    },
}
