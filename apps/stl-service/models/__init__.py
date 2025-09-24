# apps/stl-service/models/__init__.py
# Registro central de modelos. El backend importa de aquí.

from .vesa_adapter import NAME as vesa_adapter_name, TYPES as vesa_adapter_types, DEFAULTS as vesa_adapter_defaults, make_model as vesa_adapter_make
from .qr_plate import NAME as qr_plate_name, TYPES as qr_plate_types, DEFAULTS as qr_plate_defaults, make_model as qr_plate_make
from .router_mount import NAME as router_mount_name, TYPES as router_mount_types, DEFAULTS as router_mount_defaults, make_model as router_mount_make
from .cable_tray import NAME as cable_tray_name, TYPES as cable_tray_types, DEFAULTS as cable_tray_defaults, make_model as cable_tray_make
from .enclosure_ip65 import NAME as enclosure_ip65_name, TYPES as enclosure_ip65_types, DEFAULTS as enclosure_ip65_defaults, make_model as enclosure_ip65_make
from .cable_clip import NAME as cable_clip_name, TYPES as cable_clip_types, DEFAULTS as cable_clip_defaults, make_model as cable_clip_make
from .phone_stand import NAME as phone_stand_name, TYPES as phone_stand_types, DEFAULTS as phone_stand_defaults, make_model as phone_stand_make
from . import vesa_shelf
REGISTRY["vesa_shelf"] = vesa_shelf
REGISTRY = {
    vesa_adapter_name: {
        "types": vesa_adapter_types,
        "defaults": vesa_adapter_defaults,
        "make": vesa_adapter_make,
    },
    qr_plate_name: {
        "types": qr_plate_types,
        "defaults": qr_plate_defaults,
        "make": qr_plate_make,
    },
    router_mount_name: {
        "types": router_mount_types,
        "defaults": router_mount_defaults,
        "make": router_mount_make,
    },
    cable_tray_name: {
        "types": cable_tray_types,
        "defaults": cable_tray_defaults,
        "make": cable_tray_make,
    },
    enclosure_ip65_name: {
        "types": enclosure_ip65_types,
        "defaults": enclosure_ip65_defaults,
        "make": enclosure_ip65_make,
    },
    cable_clip_name: {
        "types": cable_clip_types,
        "defaults": cable_clip_defaults,
        "make": cable_clip_make,
    },
    phone_stand_name: {
        "types": phone_stand_types,
        "defaults": phone_stand_defaults,
        "make": phone_stand_make,
    },
}
