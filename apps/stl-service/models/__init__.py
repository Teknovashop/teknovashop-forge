# apps/stl-service/models/__init__.py
from typing import Callable, Dict, Any

# Registro de builders: name -> callable(params)->bytes
_registry: Dict[str, Callable[[Dict[str, Any]], bytes]] = {}


def _try_register(name: str, module_name: str, func: str = "build") -> None:
    """
    Intenta importar models.<module_name> y registrar su función 'build'.
    Si falla, no rompe el servicio; simplemente no registra esa entrada.
    """
    try:
        mod = __import__(f"models.{module_name}", fromlist=[func])
        builder = getattr(mod, func, None)
        if callable(builder):
            _registry[name] = builder  # nombre externo -> builder real
    except Exception:
        # Silencioso: algunos módulos pueden no existir en esta versión
        pass


# 1) Registra los módulos que SÍ existen en tu repo (según tu screenshot)
_try_register("cable_tray",    "cable_tray")
_try_register("cable_clip",    "cable_clip")
_try_register("enclosure_ip65","enclosure_ip65")
_try_register("headset_stand", "headset_stand")
_try_register("laptop_stand",  "laptop_stand")
_try_register("phone_stand",   "phone_stand")
_try_register("qr_plate",      "qr_plate")

# 2) Aliases de nombres usados por el front a módulos existentes
#    (NO crea ficheros nuevos; sólo mapea nombre -> builder ya registrado)
ALIASES = {
    # Tu selector llama a "Camera Plate 1/4"
    "camera_plate": "qr_plate",       # placa plana con agujero(s)

    # "USB Hub Holder"
    "hub_holder":   "cable_tray",     # bandeja/soporte en U sencillo

    # Otros nombres que tu UI podría emitir
    "vesa_adapter": "cable_tray",
    "router_mount": "cable_tray",
    "tablet_stand": "phone_stand",
    "monitor_stand":"laptop_stand",
    "mic_arm_clip": "cable_clip",
    "go_pro_mount": "cable_clip",
    "raspi_case":   "enclosure_ip65",
    "phone_dock":   "phone_stand",
    "ssd_holder":   "enclosure_ip65",
}

for alias, target in ALIASES.items():
    if alias not in _registry and target in _registry:
        _registry[alias] = _registry[target]


def build_model(name: str, params: Dict[str, Any]) -> bytes:
    builder = _registry.get(name)
    if not builder:
        # Mensaje claro si algo quedó sin resolver
        raise ValueError(f"model-not-found:{name}")
    return builder(params)
