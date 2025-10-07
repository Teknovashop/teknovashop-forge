# apps/stl-service/models/__init__.py
# Registro central de modelos. El backend importa de aquí.

# --- Núcleo: modelos existentes (deben estar) ---
from .vesa_adapter import (
    NAME as vesa_adapter_name,
    TYPES as vesa_adapter_types,
    DEFAULTS as vesa_adapter_defaults,
    make_model as vesa_adapter_make,
)
from .qr_plate import (
    NAME as qr_plate_name,
    TYPES as qr_plate_types,
    DEFAULTS as qr_plate_defaults,
    make_model as qr_plate_make,
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
from .enclosure_ip65 import (
    NAME as enclosure_ip65_name,
    TYPES as enclosure_ip65_types,
    DEFAULTS as enclosure_ip65_defaults,
    make_model as enclosure_ip65_make,
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

# Mapa principal
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

# --- Helpers ---
def _infer_types_from_defaults(defaults: dict) -> dict:
    """Dada una tabla de DEFAULTS, infiere un mapa de TYPES compatible."""
    tmap = {}
    for k, v in (defaults or {}).items():
        if isinstance(v, bool):
            tmap[k] = "bool"
        elif isinstance(v, int):
            tmap[k] = "int"
        elif isinstance(v, float):
            tmap[k] = "float"
        elif isinstance(v, str):
            tmap[k] = "str"
        elif isinstance(v, (list, tuple)):
            tmap[k] = "array"
        else:
            tmap[k] = "any"
    return tmap

def _safe_register(module_name: str, fallback_name: str):
    """
    Intenta importar un módulo de modelo opcional y registrarlo en REGISTRY.
    Acepta NAME, DEFAULTS, TYPES, y make_model/make.
    """
    try:
        module = __import__(f".{module_name}", globals(), locals(), fromlist=["*"])
    except Exception as e:
        print(f"[models] {module_name} deshabilitado: {e}")
        return

    name = getattr(module, "NAME", fallback_name)
    defaults = getattr(module, "DEFAULTS", {})
    types = getattr(module, "TYPES", None) or _infer_types_from_defaults(defaults)
    make = getattr(module, "make_model", None) or getattr(module, "make", None)
    if not callable(make):
        print(f"[models] {module_name}: no se encontró 'make_model'/'make'; no se registra")
        return

    REGISTRY[name] = {"types": types, "defaults": defaults, "make": make}
    print(f"[models] {module_name} registrado como '{name}'")

# --- Registro opcional (no bloquea si falla) ---
_safe_register("vesa_shelf", "vesa_shelf")

# --- API pública cómoda ---
MODEL_REGISTRY = REGISTRY  # alias
def available_model_slugs() -> list[str]:
    return list(REGISTRY.keys())
