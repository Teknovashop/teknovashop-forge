
"""
Autodiscovery de builders de FORGE.

Para cada módulo `models/<nombre>.py` se intentará registrar un builder con
las siguientes reglas (en orden):

1) Si define `BUILDER: Callable`, se usa.
2) Si define `BUILD: dict`, se intenta `BUILD["make"]` o `BUILD["build"]`.
3) Si expone una función `build` / `make` / `make_model` / `generate`, se usa.
4) Se crean alias snake <-> kebab automáticamente.
5) Si el módulo define `NAME: str` y/o `SLUGS: list[str]`, se añaden como alias.

Además se añaden alias “humanos” frecuentes al final.
"""

from __future__ import annotations
from typing import Callable, Dict, Iterable
import importlib
import pkgutil

# --------------------- Registro y alias globales ---------------------

REGISTRY: Dict[str, Callable] = {}
ALIASES: Dict[str, str] = {}

def _register(name_snake: str, fn: Callable) -> None:
    """Registra el callable y crea alias básicos snake/kebab."""
    key = name_snake.lower()
    REGISTRY[key] = fn
    # Alias identidad y kebab
    ALIASES.setdefault(key, key)
    ALIASES.setdefault(key.replace("_", "-"), key)

def _add_alias(raw_slug: str, target_snake: str) -> None:
    """Añade alias sin pisar entradas existentes."""
    if not raw_slug or not target_snake:
        return
    raw = raw_slug.strip().lower()
    snake = target_snake.strip().lower()
    kebab = snake.replace("_", "-")
    ALIASES.setdefault(raw, snake)
    # también su forma kebab por si llega en snake
    if "_" in raw:
        ALIASES.setdefault(raw.replace("_", "-"), snake)
    else:
        ALIASES.setdefault(raw.replace("-", "_"), snake)
    # asegúrate de que kebab->snake está
    ALIASES.setdefault(kebab, snake)

# --------------------- Descubrimiento de módulos ---------------------

# Explora módulos de primer nivel en `models/`
for _finder, _name, _ispkg in pkgutil.iter_modules(__path__):
    if _ispkg or _name in {"__init__", "text", "text_ops", "_helpers", "common"}:
        continue

    try:
        mod = importlib.import_module(f"{__name__}.{_name}")
    except Exception:
        # si un módulo falla al importar, seguimos con el resto
        continue

    # 1) Elige el builder por prioridad
    fn = getattr(mod, "BUILDER", None)
    if not callable(fn):
        build_dict = getattr(mod, "BUILD", None)
        if isinstance(build_dict, dict):
            cand = build_dict.get("make") or build_dict.get("build")
            if callable(cand):
                fn = cand
    if not callable(fn):
        for attr in ("build", "make", "make_model", "generate"):
            f = getattr(mod, attr, None)
            if callable(f):
                fn = f
                break

    if callable(fn):
        _register(_name, fn)

    # 2) Alias declarados por el módulo
    #    - NAME: str  -> alias directo
    #    - SLUGS: list -> múltiples alias
    name_alias = getattr(mod, "NAME", None)
    if isinstance(name_alias, str) and name_alias.strip():
        _add_alias(name_alias, _name)

    slugs: Iterable[str] = getattr(mod, "SLUGS", []) or []
    for s in slugs:
        if isinstance(s, str) and s.strip():
            _add_alias(s, _name)

# --------------------- Alias “humanos” adicionales -------------------

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
    # por si llegan en snake ya “humanos”
    "tablet_stand": "tablet_stand",
    "monitor_stand": "monitor_stand",
    "phone_dock": "phone_dock",
    "camera_plate": "camera_plate",
    "hub_holder": "hub_holder",
    "go_pro_mount": "go_pro_mount",
    "mic_arm_clip": "mic_arm_clip",
}
for k, v in _extra.items():
    _add_alias(k, v)

# --------------------- Utilidad opcional de texto --------------------

apply_text_ops = None  # type: ignore
for candidate in ("text", "text_ops"):
    try:
        m = importlib.import_module(f"{__name__}.{candidate}")
        if hasattr(m, "apply_text_ops"):
            apply_text_ops = getattr(m, "apply_text_ops")  # type: ignore
            break
    except Exception:
        pass

# --------------------- API de ayuda (opcional) -----------------------

def get_builder(slug_or_name: str):
    """Resuelve un slug en snake usando ALIASES y devuelve el callable."""
    if not slug_or_name:
        return None
    raw = slug_or_name.strip().lower()
    snake = ALIASES.get(raw, ALIASES.get(raw.replace("-", "_"), raw.replace("-", "_")))
    return REGISTRY.get(snake)

__all__ = ["REGISTRY", "ALIASES", "get_builder", "apply_text_ops"]
