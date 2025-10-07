# apps/stl-service/models/__init__.py
"""
Registro central de modelos (modular, escalable).
- Los módulos “core” se importan de forma estricta (si faltan, que falle para detectarlo).
- Los módulos “opcionales” se registran con _safe_register(): si no existen, se ignoran sin romper el servicio.
"""

# ---------- Core (ya presentes en tu repo) ----------
from .vesa_adapter import (
    NAME as vesa_adapter_name,
    TYPES as vesa_adapter_types,
    DEFAULTS as vesa_adapter_defaults,
    make_model as vesa_adapter_make,
)
from .router_mount import (
    NAME as router_mount_name,
    TYPES as router_mount_types,
    DEFAULTS as router_mount_defaults,
    make_model as router_mount_make,
)
from .cable_tray import (
    NAME as cable_tray_name,
    TYPES as cable_tray_types,
    DEFAULTS as cable_tray_defaults,
    make_model as cable_tray_make,
)
from .cable_clip import (
    NAME as cable_clip_name,
    TYPES as cable_clip_types,
    DEFAULTS as cable_clip_defaults,
    make_model as cable_clip_make,
)
from .phone_stand import (
    NAME as phone_stand_name,
    TYPES as phone_stand_types,
    DEFAULTS as phone_stand_defaults,
    make_model as phone_stand_make,
)
from .qr_plate import (
    NAME as qr_plate_name,
    TYPES as qr_plate_types,
    DEFAULTS as qr_plate_defaults,
    make_model as qr_plate_make,
)
from .enclosure_ip65 import (
    NAME as enclosure_ip65_name,
    TYPES as enclosure_ip65_types,
    DEFAULTS as enclosure_ip65_defaults,
    make_model as enclosure_ip65_make,
)

# Mapa principal con los “core” (estables/garantizados)
REGISTRY = {
    vesa_adapter_name: {
        "types": vesa_adapter_types,
        "defaults": vesa_adapter_defaults,
        "make": vesa_adapter_make,
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
    qr_plate_name: {
        "types": qr_plate_types,
        "defaults": qr_plate_defaults,
        "make": qr_plate_make,
    },
    enclosure_ip65_name: {
        "types": enclosure_ip65_types,
        "defaults": enclosure_ip65_defaults,
        "make": enclosure_ip65_make,
    },
}

# ---------- Helpers ----------
def _infer_types_from_defaults(defaults: dict) -> dict:
    t = {}
    for k, v in (defaults or {}).items():
        if isinstance(v, bool):
            t[k] = "bool"
        elif isinstance(v, int):
            t[k] = "int"
        elif isinstance(v, float):
            t[k] = "float"
        elif isinstance(v, str):
            t[k] = "str"
        elif isinstance(v, (list, tuple)):
            t[k] = "array"
        else:
            t[k] = "any"
    return t

def _safe_register(module_name: str, fallback_name: str):
    """
    Importa módulos opcionales sin romper si no existen.
    Requiere en el módulo: NAME, DEFAULTS y make_model/make.
    TYPES es opcional (se infiere desde DEFAULTS).
    """
    try:
        module = __import__(f".{module_name}", globals(), locals(), fromlist=["*"])
    except Exception as e:
        print(f"[models] {module_name} no disponible: {e}")
        return

    name = getattr(module, "NAME", fallback_name)
    defaults = getattr(module, "DEFAULTS", {}) or {}
    types = getattr(module, "TYPES", None) or _infer_types_from_defaults(defaults)
    make = getattr(module, "make_model", None) or getattr(module, "make", None)
    if not callable(make):
        print(f"[models] {module_name}: no hay make_model/make callable; omitido")
        return

    REGISTRY[name] = {"types": types, "defaults": defaults, "make": make}
    print(f"[models] Registrado opcional '{name}' desde {module_name}")

# ---------- Opcionales (para completar hasta ~16) ----------
# Añade aquí todos los que tengas en /apps/stl-service/models/*.py
# Los siguientes son comunes con tu catálogo (si algunos no existen, se ignoran):
for optional in [
    "camera_plate",
    "monitor_stand",
    "laptop_stand",
    "hub_holder",
    "mic_arm_clip",
    "ssd_holder",
    "tablet_stand",
    "raspi_case",
    "go_pro_mount",
    "camera_mount",    # si tienes este como módulo independiente
    "vesa_shelf",      # versión tipo repisa VESA (si existe)
]:
    _safe_register(optional, optional)

# API pública del registro
MODEL_REGISTRY = REGISTRY

def available_model_slugs() -> list[str]:
    return list(REGISTRY.keys())
