# apps/stl-service/models/__init__.py
# Registra todos los "makers" y si algún archivo no está presente
# ofrece un fallback simple para no tumbar el servicio.

import trimesh as tm

def _fallback_box(params: dict) -> tm.Trimesh:
    L = float(params.get("length", 100))
    W = float(params.get("width", 60))
    H = float(params.get("thickness", 4))
    m = tm.creation.box((L, H, W))
    m.apply_translation((L/2, H/2, W/2))
    return m

from .cable_tray import make_model as make_cable_tray
from .router_mount import make_model as make_router_mount
from .vesa_adapter import make_model as make_vesa

try:
    from .phone_stand import make_model as make_phone_stand
except Exception:
    def make_phone_stand(p: dict) -> tm.Trimesh:
        return _fallback_box(p)

try:
    from .qr_plate import make_model as make_qr_plate
except Exception:
    def make_qr_plate(p: dict) -> tm.Trimesh:
        return _fallback_box(p)

try:
    from .enclosure_ip65 import make_model as make_enclosure_ip65
except Exception:
    def make_enclosure_ip65(p: dict) -> tm.Trimesh:
        return _fallback_box(p)

try:
    from .cable_clip import make_model as make_cable_clip
except Exception:
    def make_cable_clip(p: dict) -> tm.Trimesh:
        return _fallback_box(p)

__all__ = [
    "make_cable_tray",
    "make_router_mount",
    "make_vesa",
    "make_phone_stand",
    "make_qr_plate",
    "make_enclosure_ip65",
    "make_cable_clip",
]
