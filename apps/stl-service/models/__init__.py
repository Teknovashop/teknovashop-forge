# apps/stl-service/models/__init__.py
from typing import Callable, Dict, Any

# Registro interno: nombre -> callable(params) -> bytes (STL)
_registry: Dict[str, Callable[[Dict[str, Any]], bytes]] = {}


def _try_register(name: str, module_name: str, func: str = "make_model") -> None:
    """
    Importa models.<module_name> y registra su función 'make_model'.
    Si el módulo no existe en esta versión, no rompe el servicio.
    """
    try:
        mod = __import__(f"models.{module_name}", fromlist=[func])
        builder = getattr(mod, func, None)
        if callable(builder):
            _registry[name] = builder
    except Exception:
        # No elevamos; preferimos que arranque y ya dará model-not-found
        # si alguien pide un modelo que no está.
        pass


# === REGISTRO DE MODELOS REALES (coinciden con tus .py existentes) ===
_try_register("cable_tray", "cable_tray")
_try_register("cable_clip", "cable_clip")
_try_register("camera_plate", "camera_plate")
_try_register("enclosure_ip65", "enclosure_ip65")
_try_register("headset_stand", "headset_stand")
_try_register("hub_holder", "hub_holder")
_try_register("laptop_stand", "laptop_stand")
_try_register("phone_stand", "phone_stand")
_try_register("qr_plate", "qr_plate")
_try_register("router_mount", "router_mount")
_try_register("ssd_holder", "ssd_holder")
_try_register("tablet_stand", "tablet_stand")
_try_register("vesa_adapter", "vesa_adapter")
_try_register("wall_hook", "wall_hook")

# === ALIAS para lo que manda el frontend ===
# (sin crear ficheros nuevos; solo alias a los modelos existentes)
_aliases = {
    "phone_dock": "phone_stand",   # el UI lo llama phone_dock
    # Añade aquí más alias si aparecen en el selector
    # "monitor_stand": "laptop_stand",  # (ejemplo si lo usa el UI)
    # "mic_arm_clip": "cable_clip",     # (ejemplo si lo usa el UI)
    # "go_pro_mount": "camera_plate",   # (ejemplo si lo usa el UI)
    # "raspi_case": "enclosure_ip65",   # (ejemplo si lo usa el UI)
}
for alias, target in _aliases.items():
    if target in _registry and alias not in _registry:
        _registry[alias] = _registry[target]


# 1) Tu app.py hace: from models import REGISTRY
REGISTRY: Dict[str, Callable[[Dict[str, Any]], bytes]] = _registry

# 2) Helper por compatibilidad
def build_model(name: str, params: Dict[str, Any]) -> bytes:
    builder = _registry.get(name)
    if not builder:
        raise ValueError(f"model-not-found:{name}")
    return builder(params)

__all__ = ["REGISTRY", "build_model"]
