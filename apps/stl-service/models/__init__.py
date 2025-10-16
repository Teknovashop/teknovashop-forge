# apps/stl-service/models/__init__.py
from typing import Callable, Dict, Any

# Registro interno: nombre -> callable(params) -> bytes (STL en bytes)
_registry: Dict[str, Callable[[Dict[str, Any]], bytes]] = {}


def _try_register(name: str, module_name: str, func: str = "build") -> None:
    """
    Intenta importar models.<module_name> y registrar su función 'build'.
    No rompe el servicio si el módulo no existe en esta versión.
    """
    try:
        mod = __import__(f"models.{module_name}", fromlist=[func])
        builder = getattr(mod, func, None)
        if callable(builder):
            _registry[name] = builder
    except Exception:
        # Silencioso a propósito
        pass


# --- Módulos que SÍ existen en tu repo (según los zips/capturas) ---
_try_register("cable_tray",     "cable_tray")
_try_register("cable_clip",     "cable_clip")
_try_register("enclosure_ip65", "enclosure_ip65")
_try_register("headset_stand",  "headset_stand")
_try_register("laptop_stand",   "laptop_stand")
_try_register("phone_stand",    "phone_stand")
_try_register("qr_plate",       "qr_plate")

# --- Aliases: nombres que puede enviar el front -> builders existentes ---
ALIASES = {
    # Nombres de UI -> mapeados temporalmente a módulos reales ya presentes
    "camera_plate":  "qr_plate",        # placa plana con agujeros
    "hub_holder":    "cable_tray",      # soporte tipo bandeja/U sencillo
    "vesa_adapter":  "cable_tray",
    "router_mount":  "cable_tray",
    "tablet_stand":  "phone_stand",
    "monitor_stand": "laptop_stand",
    "mic_arm_clip":  "cable_clip",
    "go_pro_mount":  "cable_clip",
    "raspi_case":    "enclosure_ip65",
    "phone_dock":    "phone_stand",
    "ssd_holder":    "enclosure_ip65",
}

for alias, target in ALIASES.items():
    if alias not in _registry and target in _registry:
        _registry[alias] = _registry[target]


# --- API pública esperada por tu app.py ---

# 1) Tu app.py puede hacer: from models import REGISTRY
#    Exponemos el dict real con el nombre EXACTO que espera.
REGISTRY: Dict[str, Callable[[Dict[str, Any]], bytes]] = _registry

# 2) También dejamos el helper build_model por compatibilidad
def build_model(name: str, params: Dict[str, Any]) -> bytes:
    builder = _registry.get(name)
    if not builder:
        raise ValueError(f"model-not-found:{name}")
    return builder(params)


__all__ = ["REGISTRY", "build_model"]
