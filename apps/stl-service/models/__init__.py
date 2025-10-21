# apps/stl-service/models/__init__.py
"""
Autodiscovery de builders de FORGE.

Detecta y registra automáticamente funciones constructoras en los módulos
del paquete `models/`. Reglas:
- Para cada módulo `models/<nombre>.py`:
    • si expone `build` / `make` / `generate`, se registra con clave snake `<nombre>`.
    • si define `SLUGS = ["tablet-stand", ...]` se crean alias extra.
    • si define `BUILDER = <func>` se usa ese callable explícito.

- Se generan alias kebab <-> snake automáticamente (ej.: `tablet-stand` -> `tablet_stand`).
- Se permiten alias “humanos” frecuentes.
"""

from __future__ import annotations
import importlib
import pkgutil
from typing import Callable, Dict, Iterable

REGISTRY: Dict[str, Callable] = {}
ALIASES: Dict[str, str] = {}

def _register(name_snake: str, fn: Callable) -> None:
    key = name_snake.lower()
    REGISTRY[key] = fn
    # alias kebab
    ALIASES.setdefault(key.replace("_", "-"), key)

# 1) Explora módulos de primer nivel en `models/`
for _finder, _name, _ispkg in pkgutil.iter_modules(__path__):
    if _ispkg:
        continue
    if _name in {"__init__", "text", "text_ops", "common"}:
        continue
    try:
        mod = importlib.import_module(f"{__name__}.{_name}")
    except Exception:
        continue

    # Elige el builder
    fn = getattr(mod, "BUILDER", None)
    if not callable(fn):
        fn = getattr(mod, "build", None) or getattr(mod, "make", None) or getattr(mod, "generate", None)
    if callable(fn):
        _register(_name, fn)

    # Alias declarados por el módulo
    slugs: Iterable[str] = getattr(mod, "SLUGS", []) or []
    for s in slugs:
        raw = str(s).strip().lower()
        snake = raw.replace("-", "_")
        ALIASES.setdefault(raw, snake)
        ALIASES.setdefault(snake.replace("_", "-"), snake)

# 2) Alias “humanos” adicionales, sin pisar existentes
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

# 3) Reexporta apply_text_ops si existe
apply_text_ops = None  # type: ignore
for candidate in ("text", "text_ops"):
    try:
        m = importlib.import_module(f"{__name__}.{candidate}")
        if hasattr(m, "apply_text_ops"):
            apply_text_ops = getattr(m, "apply_text_ops")  # type: ignore
            break
    except Exception:
        pass
