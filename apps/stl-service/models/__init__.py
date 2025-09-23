# apps/stl-service/models/__init__.py
from .cable_tray import make_model as make_cable_tray
from .router_mount import make_model as make_router_mount
from .vesa_adapter import make_model as make_vesa
from .phone_stand import make_model as make_phone_stand
from .qr_plate import make_model as make_qr_plate
from .enclosure_ip65 import make_model as make_enclosure_ip65
from .cable_clip import make_model as make_cable_clip

__all__ = [
    "make_cable_tray",
    "make_router_mount",
    "make_vesa",
    "make_phone_stand",
    "make_qr_plate",
    "make_enclosure_ip65",
    "make_cable_clip",
]
