# apps/stl-service/models/__init__.py
"""
Autodiscovery de builders y alias para FORGE.
- REGISTRY: dict[str, callable]
- ALIASES:  dict[str, str]  (kebab -> snake y sinónimos)
- apply_text_ops: se reexporta si existe
"""

from __future__ import annotations
import importlib
import pkgutil
from typing import Callable, Dict

REGISTRY: Dict[str, Callable] = {}
ALIASES: Dict[str, str] = {}

# 1) Descubre módulos "simples" con build/make/generate
for _finder, _name, _ispkg in pkgutil.iter_modules(__path__):
    if _ispkg:
        continue
    if _name in {"__init__", "text", "text_ops"}:
        continue
    mod = importlib.import_module(f"{__name__}.{_name}")
    fn = getattr(mod, "build", None) or getattr(mod, "make", None) or getattr(mod, "generate", None)
    if callable(fn):
        # clave snake_case por el nombre del módulo
        REGISTRY[_name] = fn

# 2) Alias automáticos kebab-case para todos los registrados
for key in list(REGISTRY.keys()):
    kebab = key.replace("_", "-").lower()
    ALIASES[kebab] = key

# 3) Alias “humanos” adicionales (sin sobrescribir los existentes)
_extra = {
    "vesa-adapter": "vesa_adapter",
    "router-mount": "router_mount",
    "cable-tray": "cable_tray",
    "tablet-stand": "tablet_stand",
    "monitor-stand": "monitor_stand",
    "ssd-holder": "ssd_holder",
    "raspi-case": "raspi_case",
    "go-pro-mount": "go_pro_mount",
    "gopro-mount": "go_pro_mount",
    "mic-arm-clip": "mic_arm_clip",
    "camera-plate": "camera_plate",
    "wall-hook": "wall_hook",
    "wall-bracket": "wall_bracket",
    "phone-dock": "phone_dock",
    "hub-holder": "hub_holder",
    "cable-clip": "cable_clip",
}
for k, v in _extra.items():
    ALIASES.setdefault(k, v)

# 4) Reexporta apply_text_ops si existe en alguno de los módulos comunes
apply_text_ops = None  # type: ignore
for candidate in ("text", "text_ops"):
    try:
        _m = importlib.import_module(f"{__name__}.{candidate}")
        if hasattr(_m, "apply_text_ops"):
            apply_text_ops = getattr(_m, "apply_text_ops")  # type: ignore
            break
    except Exception:
        pass
